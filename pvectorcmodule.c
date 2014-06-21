#include <Python.h>
#include <structmember.h>

/*
TODO: 
- Python 3 compatibility?
- PyPy compatibility
- contains, count
- Fix automated memory leak tests (eg. check memory usage, run for a while and check it again)
- Test to optimize by creating a node pool and reuse deallocated nodes instead of allocating new ones
- Create optimized function for replacing multiple elements in the same function call
- Register with Hashable

Persistant/Immutable data structures. Unfortunately I have not been able to come
up with an implementation that is 100% immutable due to the ref counts used by
Python internally so the GIL must still be at work...

To the end user they should appear immutable at least.

Naming conventions
------------------
initpyrsistentc - This is the method that initializes the whole module
pyrsistent_* -    Methods part of the interface
Pvector_*    -    Instance methods of the PVector object

All other methods are camel cased without prefix. All methods are static, none should
require to be exposed outside of this module. 
*/

#define BRANCH_FACTOR 32
#define BIT_MASK (BRANCH_FACTOR - 1)

static PyTypeObject PVectorType;

int SHIFT = 0;

typedef struct {
  void *items[BRANCH_FACTOR];
  unsigned int refCount;
} VNode;

typedef struct {
  PyObject_HEAD
  unsigned int count;   // Perhaps ditch this one in favor of ob_size/Py_SIZE()
  unsigned int shift;
  VNode *root;
  VNode *tail;
} PVector;

static PVector* EMPTY_VECTOR = NULL;

// No access to internal members
static PyMemberDef PVector_members[] = {
	{NULL}  /* Sentinel */
};


#define debug(...)
// #define debug printf

static VNode* newNode(void) {
  VNode* result = malloc(sizeof(VNode));
  memset(result, 0x0, sizeof(VNode));
  result->refCount = 1;
  debug("newNode() %p\n", result);
  return result;
}

static VNode* copyNode(VNode* source) {
  /* NB: Only to be used for internal nodes, eg. nodes that do not
         hold direct references to python objects but only to other nodes. */
  int i;
  VNode* result = malloc(sizeof(VNode));
  debug("copyNode() %p\n", result);
  memcpy(result->items, source->items, sizeof(source->items));
  
  for(i = 0; i < BRANCH_FACTOR; i++) {
    if(result->items[i] != NULL) {
      ((VNode*)result->items[i])->refCount++;
    }
  }

  result->refCount = 1;
  return result;
}

static PVector* emptyNewPvec(void);
static PVector* copyPVector(PVector *original);
static void extend_with_item(PVector *newVec, PyObject *item);

static void freeNode(VNode* node) {
  free(node);
}


static Py_ssize_t PVector_len(PVector *self) {
  return self->count;
}

/* Convenience macros */
#define ROOT_NODE_FULL(vec) ((vec->count >> SHIFT) > (1 << vec->shift))
#define TAIL_OFF(vec) ((vec->count < BRANCH_FACTOR) ? 0 : (((vec->count - 1) >> SHIFT) << SHIFT))
#define TAIL_SIZE(vec) (vec->count - TAIL_OFF(vec))
#define PVector_CheckExact(op) (Py_TYPE(op) == &PVectorType)

static VNode* nodeFor(PVector *self, int i){
  int level;
  if((i >= 0) && (i < self->count)) {
    if(i >= TAIL_OFF(self)) {
      return self->tail;
    }

    VNode* node = self->root;
    for(level = self->shift; level > 0; level -= SHIFT) {
      node = (VNode*) node->items[(i >> level) & BIT_MASK];
    }

    return node;
  }

  PyErr_SetString(PyExc_IndexError, "Index out of range");
  return NULL;
}

/*
 Returns a new reference as specified by the PySequence_GetItem function.
*/
static PyObject* _get_item(PVector *self, Py_ssize_t pos) {
  VNode* node = nodeFor((PVector*)self, pos);

  if(node != NULL) {
    return node->items[pos & BIT_MASK];
  }

  return NULL;
}


static PyObject* PVector_get_item(PVector *self, Py_ssize_t pos) {
  if (pos < 0) {
    pos += self->count;
  }

  PyObject* obj = _get_item(self, pos);
  Py_XINCREF(obj);
  return obj;  
}

static void releaseNode(int level, VNode *node) {
  if(node == NULL) {
    return;
  }

  debug("releaseNode(): node=%p, level=%i, refCount=%i\n", node, level, node->refCount);

  int i;

  node->refCount--;
  if(node->refCount == 0) {
    if(level > 0) {
      for(i = 0; i < BRANCH_FACTOR; i++) {
        if(node->items[i] != NULL) {
          releaseNode(level - SHIFT, node->items[i]);
        }
      }
      freeNode(node);
    } else {
      for(i = 0; i < BRANCH_FACTOR; i++) {
         Py_XDECREF(node->items[i]);
      }
      freeNode(node);
    }
  }

  debug("releaseNode(): Done! node=%p!\n", node);
}

/*
 Returns all references to PyObjects that have been stolen. Also decrements
 the internal reference counts used for shared memory structures and deallocates
 those if needed.
*/
static void PVector_dealloc(PVector *self) {
  debug("Dealloc(): self=%p, self->count=%i, tail->refCount=%i, root->refCount=%i, self->shift=%i, self->tail=%p, self->root=%p\n",
   self, self->count, self->tail->refCount, self->root->refCount, self->shift, self->tail, self->root, self->root);

  PyObject_GC_UnTrack((PyObject*)self);
  Py_TRASHCAN_SAFE_BEGIN(self)

  releaseNode(0, self->tail);
  releaseNode(self->shift, self->root);
  
  PyObject_GC_Del(self);
  Py_TRASHCAN_SAFE_END(self)
}

static PyObject *PVector_repr(PVector *self) {
  // Reuse the tuple repr code, a bit less efficient but saves some code
  Py_ssize_t i;
  i = Py_ReprEnter((PyObject *)self);
  if (i != 0) {
    return i > 0 ? PyString_FromString("(...)") : NULL;
  }

  PyObject *tuple = PyTuple_New(self->count);
  for (i = 0; i < self->count; ++i) {
    PyObject *o = _get_item(self, i);
    Py_INCREF(o);
    PyTuple_SET_ITEM(tuple, i, o);
  }

  PyObject *result = PyObject_Repr(tuple);

  Py_DECREF(tuple);
  Py_ReprLeave((PyObject *)self);
  return result;
}

static long PVector_hash(PVector *self) {
  // Follows the pattern of the tuple hash
  long x, y;
  Py_ssize_t i;
  long mult = 1000003L;
  x = 0x456789L;
  for(i=0; i<self->count; i++) {
      y = PyObject_Hash(_get_item(self, i));
      if (y == -1) {
        return -1;
      }
      x = (x ^ y) * mult;
      mult += (long)(82520L + i + i);
  }

  x += 97531L;
  if(x == -1) {
    x = -2;
  }

  return x;
}

static PyObject* compareSizes(long vlen, long wlen, int op) {
    int cmp;
    PyObject *res;
    switch (op) {
      case Py_LT: cmp = vlen <  wlen; break;
      case Py_LE: cmp = vlen <= wlen; break;
      case Py_EQ: cmp = vlen == wlen; break;
      case Py_NE: cmp = vlen != wlen; break;
      case Py_GT: cmp = vlen >  wlen; break;
      case Py_GE: cmp = vlen >= wlen; break;
      default: return NULL; /* cannot happen */
    }
    
    if (cmp) {
      res = Py_True;
    } else {
      res = Py_False;
    }

    Py_INCREF(res);
    return res;
}

static PyObject* PVector_richcompare(PyObject *v, PyObject *w, int op) {
    // Follows the principles of the tuple comparison
    PVector *vt, *wt;
    Py_ssize_t i;
    Py_ssize_t vlen, wlen;

    if(!PVector_CheckExact(v) || !PVector_CheckExact(w)) {
        Py_INCREF(Py_NotImplemented);
        return Py_NotImplemented;
    }

    if((op == Py_EQ) && (v == w)) {
        Py_INCREF(Py_True);
        return Py_True;
    }

    vt = (PVector *)v;
    wt = (PVector *)w;

    vlen = vt->count;
    wlen = wt->count;

    /* Search for the first index where items are different. */
    PyObject *left = NULL;
    PyObject *right = NULL;
    for (i = 0; i < vlen && i < wlen; i++) {
        left = _get_item(vt, i);
        right = _get_item(wt, i);
        int k = PyObject_RichCompareBool(left, right, Py_EQ);
        if (k < 0) {
            return NULL;
        }
        if (!k) {
            break;
        }
    }

    if (i >= vlen || i >= wlen) {
        /* No more items to compare -- compare sizes */
        return compareSizes(vlen, wlen, op);
    }

    /* We have an item that differs -- shortcuts for EQ/NE */
    if (op == Py_EQ) {
        Py_INCREF(Py_False);
        return Py_False;
    } else if (op == Py_NE) {
        Py_INCREF(Py_True);
        return Py_True;
    } else {
      /* Compare the final item again using the proper operator */
      return PyObject_RichCompare(left, right, op);
    }
}


static PyObject* PVector_repeat(PVector *self, Py_ssize_t n) {
  if (n < 0) {
      n = 0;
  }

  if ((n == 0) || (self->count == 0)) {
    Py_INCREF(EMPTY_VECTOR);
    return (PyObject *)EMPTY_VECTOR;
  } else if (n == 1) {
    Py_INCREF(self);
    return (PyObject *)self;
  } else if ((self->count * n)/self->count != n) {
    return PyErr_NoMemory();
  } else {
    int i, j;
    PVector *newVec = copyPVector(self);
    for(i=0; i<(n-1); i++) {
      for(j=0; j<self->count; j++) {
        extend_with_item(newVec, PVector_get_item(self, j));
      }
    }
    return (PyObject*)newVec;
  }
}

static int PVector_traverse(PVector *o, visitproc visit, void *arg) {
    // Naive traverse
    Py_ssize_t i;
    for (i = o->count; --i >= 0; ) {
      Py_VISIT(_get_item(o, i));
    }

    return 0;
}


static void copyInsert(void** dest, void** src, Py_ssize_t pos, void *obj) {
  memcpy(dest, src, BRANCH_FACTOR * sizeof(void*));
  dest[pos] = obj;
}

static PyObject* PVector_append(PVector *self, PyObject *obj);

static PyObject* PVector_assoc(PVector *self, PyObject *obj);

static PyObject* PVector_subscript(PVector* self, PyObject* item);

static PyObject* PVector_extend(PVector *self, PyObject *args);

static PySequenceMethods PVector_sequence_methods = {
    (lenfunc)PVector_len,            /* sq_length */
    (binaryfunc)PVector_extend,      /* sq_concat */
    (ssizeargfunc)PVector_repeat,    /* sq_repeat */
    (ssizeargfunc)PVector_get_item,  /* sq_item */
    NULL,                            /* sq_slice */
    NULL,                            /* sq_ass_item */
    NULL,                            /* sq_ass_slice */
    NULL,                            /* sq_contains */
    NULL,                            /* sq_inplace_concat */
    NULL,                            /* sq_inplace_repeat */
};

static PyMappingMethods PVector_mapping_methods = {
    (lenfunc)PVector_len,
    (binaryfunc)PVector_subscript,
    NULL
};


static PyMethodDef PVector_methods[] = {
	{"append",      (PyCFunction)PVector_append, METH_O,       "Appends an element"},
	{"assoc",       (PyCFunction)PVector_assoc,  METH_VARARGS, "Inserts an element at the specified position"},
	{"__getitem__", (PyCFunction)PVector_subscript, METH_O|METH_COEXIST, "Subscript"},
	{"extend",      (PyCFunction)PVector_extend, METH_O|METH_COEXIST, "Extend"},
	{NULL}
};

static PyObject * PVectorIter_iter(PyObject *seq);

static PyTypeObject PVectorType = {
  PyObject_HEAD_INIT(NULL)
  0,
  "pyrsistent.PVector",                       /* tp_name        */
  sizeof(PVector),                            /* tp_basicsize   */
  0,		                              /* tp_itemsize    */
  (destructor)PVector_dealloc,                /* tp_dealloc     */
  0,                                          /* tp_print       */
  0,                                          /* tp_getattr     */
  0,                                          /* tp_setattr     */
  0,                                          /* tp_compare     */
  (reprfunc)PVector_repr,                     /* tp_repr        */
  0,                                          /* tp_as_number   */
  &PVector_sequence_methods,                  /* tp_as_sequence */
  &PVector_mapping_methods,                   /* tp_as_mapping  */
  (hashfunc)PVector_hash,                     /* tp_hash        */
  0,                                          /* tp_call        */
  0,                                          /* tp_str         */
  0,                                          /* tp_getattro    */
  0,                                          /* tp_setattro    */
  0,                                          /* tp_as_buffer   */
  Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,    /* tp_flags       */
  "Persistent vector",   	              /* tp_doc         */
  (traverseproc)PVector_traverse,             /* tp_traverse       */
  0,                                          /* tp_clear          */
  PVector_richcompare,                        /* tp_richcompare    */
  0,                                          /* tp_weaklistoffset */
  PVectorIter_iter,                           /* tp_iter           */
  0,                                          /* tp_iternext       */
  PVector_methods,                            /* tp_methods        */
  PVector_members,                            /* tp_members        */
  0,                                          /* tp_getset         */
  0,                                          /* tp_base           */
  0,                                          /* tp_dict           */
  0,                                          /* tp_descr_get      */
  0,                                          /* tp_descr_set      */
  0,                                          /* tp_dictoffset     */
};

static PyObject* pyrsistent_pvec(PyObject *self, PyObject *args) {
    debug("pyrsistent_pvec(): %x\n", args);

    PyObject *argObj = NULL;  /* list of arguments */

    if(!PyArg_ParseTuple(args, "|O", &argObj)) {
      return NULL;
    }

    if(argObj == NULL) {
      Py_INCREF(EMPTY_VECTOR);
      return (PyObject*)EMPTY_VECTOR;
    }

    return PVector_extend(EMPTY_VECTOR, argObj);
}

static PVector* emptyNewPvec(void) {
  PVector *pvec = PyObject_GC_New(PVector, &PVectorType);
  debug("pymem alloc_new %x, ref cnt: %u\n", pvec, pvec->ob_refcnt);
  pvec->count = (Py_ssize_t)0;
  pvec->shift = SHIFT;
  pvec->root = newNode();
  pvec->tail = newNode();
  PyObject_GC_Track((PyObject*)pvec);
  return pvec;
}

static void incRefs(PyObject **obj) {
  int i;
  for(i = 0; i < BRANCH_FACTOR; i++) {
    Py_XINCREF(obj[i]);
  }
}

static PVector* newPvec(unsigned int count, unsigned int shift, VNode *root) {
  PVector *pvec = PyObject_GC_New(PVector, &PVectorType);
  debug("pymem alloc_copy %x, ref cnt: %u\n", pvec, pvec->ob_refcnt);
  pvec->count = count;
  pvec->shift = shift;
  pvec->root = root;
  pvec->tail = newNode();
  PyObject_GC_Track((PyObject*)pvec);
  return pvec;
}

static VNode* newPath(unsigned int level, VNode* node){
  if(level == 0) {
    node->refCount++;
    return node;
  }
  
  VNode* result = newNode();
  result->items[0] = newPath(level - SHIFT, node);
  return result;
}

static VNode* pushTail(unsigned int level, unsigned int count, VNode* parent, VNode* tail) {
  int sub_index = ((count - 1) >> level) & BIT_MASK;
  VNode* result = copyNode(parent);
  VNode* nodeToInsert;
  VNode* child;
  debug("pushTail(): count = %i, sub_index = %i\n", count, sub_index);

  if(level == SHIFT) {
    // We're at the bottom
    tail->refCount++;
    nodeToInsert = tail;
  } else {
    // More levels available in the tree
    child = parent->items[sub_index];

    if(child != NULL) {
      nodeToInsert = pushTail(level - SHIFT, count, child, tail);

      // Need to make an adjustment of the refCount for the child node here since
      // it was incremented in an earlier stage when the node was copied. Now the child
      // node will be part of the path copy so the number of references to the original
      // child will not increase at all.
      child->refCount--;
    } else {
      nodeToInsert = newPath(level - SHIFT, tail);
    }
  }
  
  result->items[sub_index] = nodeToInsert;
  return result;
}

static PVector* copyPVector(PVector *original) {
  PVector *newVec = newPvec(original->count, original->shift, original->root);
  original->root->refCount++;
  memcpy(newVec->tail->items, original->tail->items, TAIL_SIZE(original) * sizeof(void*));
  incRefs((PyObject**)newVec->tail->items);
  return newVec;
}

/* Does not steal a reference, this must be managed outside of this function */
static void extend_with_item(PVector *newVec, PyObject *item) {
  unsigned int tail_size = TAIL_SIZE(newVec);

  if(tail_size >= BRANCH_FACTOR) {
    VNode* new_root;
    if(ROOT_NODE_FULL(newVec)) {
      new_root = newNode();
      new_root->items[0] = newVec->root;
      new_root->items[1] = newPath(newVec->shift, newVec->tail);
      newVec->shift += SHIFT;
    } else {
      new_root = pushTail(newVec->shift, newVec->count, newVec->root, newVec->tail);
      releaseNode(newVec->shift, newVec->root);
    }

    newVec->root = new_root;

    // Need to adjust the refCount of the old tail here since no new references were
    // actually created, we just moved the tail.
    newVec->tail->refCount--;
    newVec->tail = newNode();
    tail_size = 0;
  }

  newVec->tail->items[tail_size] = item;    
  newVec->count++;
}


static PyObject *PVector_subscript(PVector* self, PyObject* item) {
    if (PyIndex_Check(item)) {
      Py_ssize_t i = PyNumber_AsSsize_t(item, PyExc_IndexError);
      if (i == -1 && PyErr_Occurred()) {
         return NULL;
      }

      return PVector_get_item(self, i);
    } else if (PySlice_Check(item)) {
      Py_ssize_t start, stop, step, slicelength, cur, i;
      if (PySlice_GetIndicesEx((PySliceObject *)item, self->count,
             &start, &stop, &step, &slicelength) < 0) {
         return NULL;
      }

      debug("start=%i, stop=%i, step=%i\n", start, stop, step);

      if (slicelength <= 0) {
        Py_INCREF(EMPTY_VECTOR);
        return (PyObject*)EMPTY_VECTOR;
      } else if((slicelength == self->count) && (step > 0)) {
        Py_INCREF(self);
        return (PyObject*)self;
      } else {
        PVector *newVec = copyPVector(EMPTY_VECTOR);
        for (cur=start, i=0; i<slicelength; cur += (size_t)step, i++) {
          extend_with_item(newVec, PVector_get_item(self, cur));
        }

        return (PyObject*)newVec;
      }
    } else {
      PyErr_Format(PyExc_TypeError, "pvector indices must be integers, not %.200s", item->ob_type->tp_name);
      return NULL;
    }
} 

/* A hack to get some of the error handling code away from the function
   doing the actual work */
#define HANDLE_ITERATION_ERROR()                         \
    if (PyErr_Occurred()) {                              \
      if (PyErr_ExceptionMatches(PyExc_StopIteration)) { \
        PyErr_Clear();                                   \
      } else {                                           \
        return NULL;                                     \
      }                                                  \
    }


/* Returns a new vector that is extended with the iterable b.
   Takes a copy of the original vector and performs the extension in place on this
   one for efficiency. 

   These are some optimizations that could be done to this function,
   these are not considered important enough yet though.
   - Only copy the original tail if it is not full
   - No need to try to increment ref count in tail for the whole tail
*/
static PyObject* PVector_extend(PVector *self, PyObject *iterable) {
    PyObject *it;      /* iter(v) */
    PyObject *(*iternext)(PyObject *);

    it = PyObject_GetIter(iterable);
    if (it == NULL) {
        return NULL;
    }
    
    iternext = *it->ob_type->tp_iternext;
    PyObject *item = iternext(it);
    if (item == NULL) {
      Py_DECREF(it);
      HANDLE_ITERATION_ERROR()
      Py_INCREF(self);
      return (PyObject *)self;
    } else {
      PVector *newVec = copyPVector(self);
      while(item != NULL) {
        extend_with_item(newVec, item);
        item = iternext(it);
      }

      Py_DECREF(it);
      HANDLE_ITERATION_ERROR()
      return (PyObject*)newVec;
    }
}

/*
 Steals a reference to the object that is appended to the list.
 Haven't really decided if this is the right thing to do yet...
*/
static PyObject* PVector_append(PVector *self, PyObject *obj) {
  assert (obj != NULL);

  unsigned int tail_size = TAIL_SIZE(self);
  debug("append(): count = %u, tail_size = %u\n", self->count, tail_size);

  // Does the new object fit in the tail? If so, take a copy of the tail and
  // insert the new element in that.
  if(tail_size < BRANCH_FACTOR) {
    self->root->refCount++;
    PVector *new_pvec = newPvec(self->count + 1, self->shift, self->root);
    copyInsert(new_pvec->tail->items, self->tail->items, tail_size, obj);
    incRefs((PyObject**)new_pvec->tail->items);
    debug("append(): new_pvec=%p, new_pvec->tail=%p, new_pvec->root=%p\n",
    new_pvec, new_pvec->tail, new_pvec->root);

    return (PyObject*)new_pvec;
  }

  // Tail is full, need to push it into the tree  
  VNode* new_root;
  unsigned int new_shift;
  if(ROOT_NODE_FULL(self)) {
    new_root = newNode();
    new_root->items[0] = self->root;
    self->root->refCount++;
    new_root->items[1] = newPath(self->shift, self->tail);
    new_shift = self->shift + SHIFT;
  } else {
    new_root = pushTail(self->shift, self->count, self->root, self->tail);
    new_shift = self->shift;
  }

  PVector* pvec = newPvec(self->count + 1, new_shift, new_root);
  pvec->tail->items[0] = obj;
  Py_XINCREF(obj);
  debug("append_push(): pvec=%p, pvec->tail=%p, pvec->root=%p\n", pvec, pvec->tail, pvec->root);
  return (PyObject*)pvec;
}

static VNode* doAssoc(VNode* node, unsigned int level, unsigned int position, PyObject* value) {
  if(level == 0) {
    debug("doAssoc(): level == 0\n");
    VNode* theNewNode = newNode();
    copyInsert(theNewNode->items, node->items, position & BIT_MASK, value);
    incRefs((PyObject**)theNewNode->items);
    return theNewNode;
  } else {
    debug("doAssoc(): level == %i\n", level);
    VNode* theNewNode = copyNode(node);
    Py_ssize_t index = (position >> level) & BIT_MASK;

    // Drop reference to this node since we're about to replace it
    ((VNode*)theNewNode->items[index])->refCount--;
    theNewNode->items[index] = doAssoc(node->items[index], level - SHIFT, position, value); 
    return theNewNode;
  }
}


/*
 Steals a reference to the object that is inserted in the vector.
*/
static PyObject* PVector_assoc(PVector *self, PyObject *args) {
  PyObject *argObj = NULL;  /* list of arguments */
  Py_ssize_t position;

  /* The n parses for size, the O parses for a Python object */
  if(!PyArg_ParseTuple(args, "nO", &position, &argObj)) {
    return NULL;
  }

  if((0 <= position) && (position < self->count)) {
    if(position >= TAIL_OFF(self)) {
      // Reuse the root, replace the tail
      self->root->refCount++;
      PVector *new_pvec = newPvec(self->count, self->shift, self->root);
      copyInsert(new_pvec->tail->items, self->tail->items, position & BIT_MASK, argObj);
      incRefs((PyObject**)new_pvec->tail->items);
      return (PyObject*)new_pvec;
    } else {
      // Keep the tail, replace the root
      VNode *newRoot = doAssoc(self->root, self->shift, position, argObj);
      PVector *new_pvec = newPvec(self->count, self->shift, newRoot);

      // Free the tail and replace it with a reference to the tail of the original vector
      freeNode(new_pvec->tail);
      new_pvec->tail = self->tail;
      self->tail->refCount++;
      return (PyObject*)new_pvec;
    }
  } else if (position == self->count) {
    return PVector_append(self, argObj);
  } else {
    PyErr_SetString(PyExc_IndexError, "Index out of range");
    return NULL;
  }
}


static PyMethodDef PyrsistentMethods[] = {
  {"_pvector", pyrsistent_pvec, METH_VARARGS, "Factory method for persistent vectors"},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initpvectorc(void) {
  PyObject* m;
  
  // Only allow creation/initialization through factory method pvec
  PVectorType.tp_init = NULL;
  PVectorType.tp_new = NULL;

  // TODO: Perhaps make it use a proper constructor instead of a factory method
  //       and name the type pvector so that testing with instanceof or type becomes
  //       more straight forward?


  if (PyType_Ready(&PVectorType) < 0)
    return;

  // Register with Sequence to appear as a proper sequence to the outside world
  PyObject* module = PyImport_ImportModule("collections");
  PyObject* moduleDict = PyModule_GetDict(module);
  PyObject* c = PyDict_GetItemString(moduleDict, "Sequence");

  if (PyType_Ready(c->ob_type) < 0) {
    printf("Failed to initialize Sequence!\n");
    return;
  }

  if(c == NULL) {
    debug("Was NULL!\n");
  }
  
  PyObject_CallMethod(c, "register", "O", &PVectorType);

  m = Py_InitModule("pvectorc", PyrsistentMethods);

  if (m == NULL)
    return;

  SHIFT = __builtin_popcount(BIT_MASK);
  
  if(EMPTY_VECTOR == NULL) {
    EMPTY_VECTOR = emptyNewPvec();
  }

  Py_INCREF(&PVectorType);
  PyModule_AddObject(m, "PVector", (PyObject *)&PVectorType);
}


/*********************** PVector Iterator **************************/

/* 
The Sequence class provides us with a default iterator but the runtime
overhead of using that compared to the iterator below is huge.
*/

typedef struct {
    PyObject_HEAD
    Py_ssize_t it_index;
    PVector *it_seq; /* Set to NULL when iterator is exhausted */
} PVectorIter;

static void PVectorIter_dealloc(PVectorIter *);
static int PVectorIter_traverse(PVectorIter *, visitproc, void *);
static PyObject *PVectorIter_next(PVectorIter *);

static PyMethodDef PVectorIter_methods[] = {
    {NULL,              NULL}           /* sentinel */
};

PyTypeObject PVectorIterType = {
    PyVarObject_HEAD_INIT(&PyType_Type, 0)
    "pvector_iterator",                         /* tp_name */
    sizeof(PVectorIter),                        /* tp_basicsize */
    0,                                          /* tp_itemsize */
    /* methods */
    (destructor)PVectorIter_dealloc,            /* tp_dealloc */
    0,                                          /* tp_print */
    0,                                          /* tp_getattr */
    0,                                          /* tp_setattr */
    0,                                          /* tp_compare */
    0,                                          /* tp_repr */
    0,                                          /* tp_as_number */
    0,                                          /* tp_as_sequence */
    0,                                          /* tp_as_mapping */
    0,                                          /* tp_hash */
    0,                                          /* tp_call */
    0,                                          /* tp_str */
    PyObject_GenericGetAttr,                    /* tp_getattro */
    0,                                          /* tp_setattro */
    0,                                          /* tp_as_buffer */
    Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,    /* tp_flags */
    0,                                          /* tp_doc */
    (traverseproc)PVectorIter_traverse,         /* tp_traverse */
    0,                                          /* tp_clear */
    0,                                          /* tp_richcompare */
    0,                                          /* tp_weaklistoffset */
    PyObject_SelfIter,                          /* tp_iter */
    (iternextfunc)PVectorIter_next,             /* tp_iternext */
    PVectorIter_methods,                        /* tp_methods */
    0,                                          /* tp_members */
};


static PyObject * PVectorIter_iter(PyObject *seq) {
    PVectorIter *it = PyObject_GC_New(PVectorIter, &PVectorIterType);
    if (it == NULL)
        return NULL;
    it->it_index = 0;
    Py_INCREF(seq);
    it->it_seq = (PVector *)seq;
    PyObject_GC_Track(it);
    return (PyObject *)it;
}

static void PVectorIter_dealloc(PVectorIter *it) {
    PyObject_GC_UnTrack(it);
    Py_XDECREF(it->it_seq);
    PyObject_GC_Del(it);
}

static int PVectorIter_traverse(PVectorIter *it, visitproc visit, void *arg) {
    Py_VISIT(it->it_seq);
    return 0;
}

static PyObject *PVectorIter_next(PVectorIter *it) {
    assert(it != NULL);
    PVector *seq = it->it_seq;
    if (seq == NULL)
        return NULL;

    if (it->it_index < seq->count) {
        PyObject *item = _get_item(seq, it->it_index);
        ++it->it_index;
        Py_INCREF(item);
        return item;
    }

    Py_DECREF(seq);
    it->it_seq = NULL;
    return NULL;
}
