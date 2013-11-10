#include <Python.h>
#include <structmember.h>

/*
TODO: 
- Python 3 compatibility?
- Factory method for vector, implement transient vector for efficient initialization
- Support garbage collection (cycle detection)
- Code clean up
- Memory check
- Investigate seg fault in unit tests
(- Iterator)
*/

/*
Persistant/Immutable data structures. Unfortunately I have not been able to come
up with an implementation that is 100% immutable due to the ref counts used by
Python internally so the GIL must still be at work...

To the end user they should appear immutable at least.

Naming conventions
------------------
initpyrsistentc - This is the method that initializes the whole module
pyrsistent_* -    Methods part of the interface
Pvector_*    -    Instance methods of the PVector object

All other methods are camel cased without prefix. All methods are static, none should require to be exposed 
outside of this module. 

*/

#define BRANCH_FACTOR 32
#define BIT_MASK (BRANCH_FACTOR - 1)

int SHIFT = 0;

typedef struct {
  unsigned int refCount;
  void *items[BRANCH_FACTOR];
} VNode;

typedef struct {
  PyObject_HEAD
  // Needs dict here to be compatible with base class,
  // tp_dictoffset points to this location after initialization in
  // PyType_Ready. Found that out after hours of debugging... 
  PyObject *dict; 
  unsigned int count;
  unsigned int shift;
  VNode *root;
  VNode *tail;
} PVector;


// No access to internal members
static PyMemberDef PVector_members[] = {
	{NULL}  /* Sentinel */
};

static int nodeCount = 0;

static void debug(char* fmt, ...) {
  va_list args;
  va_start(args, fmt);
  printf(fmt, args);
  va_end(args);
}

static VNode* newNode() {
  VNode* result = malloc(sizeof(VNode));
  printf("meminfo malloc_new %x\n", result);
  memset(result, 0x0, sizeof(VNode));
  result->refCount = 1;
  nodeCount++;
  debug("newNode() Node count = %i\n", nodeCount);
  return result;
}

static VNode* copyNode(VNode* source) {
  int i = 0;
  VNode* result = malloc(sizeof(VNode));
  printf("meminfo malloc_copy %x\n", result);
  memcpy(result->items, source->items, sizeof(source->items));
  
  // Need to increment the reference count of the pointed
  // at objects here.
  for(i = 0; i < BRANCH_FACTOR; i++) {
    if(result->items[i] != NULL) {
      ((VNode*)result->items[i])->refCount++;
    }
  }

  result->refCount = 1;
  nodeCount++;
  debug("copyNode(): Node count = %i\n", nodeCount);
  return result;
}

static void freeNode(VNode* node) {
  free(node);
  nodeCount--;
  //printf("meminfo free %x\n", node);
  debug("freeNode(): Node count = %i\n", nodeCount);
}


static Py_ssize_t PVector_len(PVector *self) {
  return self->count;
}


static Py_ssize_t tailOff(PVector *self) {
  if(self->count < BRANCH_FACTOR) {
    return 0;
  }
  
  return ((self->count - 1) >> SHIFT) << SHIFT;
}


static VNode* nodeFor(PVector *self, int i){
  int level;
  if((i >= 0) && (i < self->count)) {
    if(i >= tailOff(self)) {
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
static PyObject* PVector_get_item(PVector *self, unsigned int pos) {
  VNode* node = nodeFor(self, pos);
  
  if(node != NULL) {
    PyObject* obj = (PyObject*)node->items[pos & BIT_MASK];
    Py_INCREF(obj);
    return obj;
  }

  return NULL;
}

static void releaseNode(int level, VNode *node) {
  // TODO: Refactor and clean up this function
  if(node == NULL) {
    return;
  }

  debug("releaseNode(): node=%x, level=%i, refCount=%i\n", node, level, node->refCount);

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
  } else if (node->refCount < 0) {
    // Strictly for error checking, this means that the refcount was never increased
    printf("Trying to deallocate node without refCount. This is most likely wrong! node = %x, refCount = %x", 
	   node, node->refCount);
  }

  debug("releaseNode(): Done! node=%x!\n", node);
}

/*
 Returns all references to PyObjects that have been stolen. Also decrements
 the internal reference counts used for shared memory structures and deallocates
 those if needed.
*/
static void PVector_dealloc(PVector *self) {
  debug("Dealloc(): self=%x, self->count=%i, tail->refCount=%i, root->refCount=%i, self->shift=%i\n", self, self->count, self->tail->refCount, self->root->refCount, self->shift);
  debug("Dealloc(): Releasing self->tail=%x\n", self->tail);
  releaseNode(0, self->tail);
  debug("Dealloc(): Releasing self->root=%x\n", self->root);
  releaseNode(self->shift, self->root);

  Py_DECREF(self->dict);
  debug("Dealloc(): Done!\n");
 
  debug("pymem del %x\n", self);
  self->ob_type->tp_free((PyObject*)self);
  //  PyObject_Del(self);
}

static void copyInsert(void** dest, void** src, Py_ssize_t pos, void *obj) {
  memcpy(dest, src, BRANCH_FACTOR * sizeof(void*));
  dest[pos] = obj;
}

static PyObject* PVector_append(PVector *self, PyObject *obj);

static PyObject* PVector_assoc(PVector *self, PyObject *obj);

static PySequenceMethods PVector_sequence_methods = {
    PVector_len,                  /* sq_length */
    NULL,                         /* sq_concat */
    NULL,                         /* sq_repeat */
    PVector_get_item,             /* sq_item */
    NULL,                         /* sq_slice */
    NULL,                         /* sq_ass_item */
    NULL,                         /* sq_ass_slice */
    NULL,                         /* sq_contains */
    NULL,                         /* sq_inplace_concat */
    NULL,                         /* sq_inplace_repeat */
};

static PyMethodDef PVector_methods[] = {
	{"append",  (PyCFunction)PVector_append, METH_O,       "Appends an element"},
	{"assoc",   (PyCFunction)PVector_assoc,  METH_VARARGS, "Inserts an element at the specified position"},
	{NULL}
};

static PyTypeObject PVectorType = {
  PyObject_HEAD_INIT(NULL)
  0,
  "pyrsistent.PVector",		/* tp_name        */
  sizeof(PVector),    		/* tp_basicsize   */
  0,				/* tp_itemsize    */
  (destructor)PVector_dealloc,				/* tp_dealloc     */
  0,				/* tp_print       */
  0,				/* tp_getattr     */
  0,				/* tp_setattr     */
  0,				/* tp_compare     */
  0,				/* tp_repr        */
  0,				/* tp_as_number   */
  &PVector_sequence_methods,	/* tp_as_sequence */
  0,				/* tp_as_mapping  */
  0,				/* tp_hash        */
  0,				/* tp_call  TODO  */
  0,				/* tp_str         */
  0,				/* tp_getattro    */
  0,				/* tp_setattro    */
  0,				/* tp_as_buffer   */
  Py_TPFLAGS_DEFAULT,		/* tp_flags       */
  "Persistent vector",   	/* tp_doc         */
  0,				/* tp_traverse       */
  0,				/* tp_clear          */
  0,				/* tp_richcompare    */
  0,				/* tp_weaklistoffset */
  0,				/* tp_iter           */ // TODO
  0,				/* tp_iternext       */ // TODO
  PVector_methods,	        /* tp_methods        */
  PVector_members,		/* tp_members        */
  0,				/* tp_getset         */
  0,				/* tp_base           */
  0,				/* tp_dict           */
  0,				/* tp_descr_get      */
  0,				/* tp_descr_set      */
  0,				/* tp_dictoffset     */
  0,
  0,
  0,

};

static PVector* EMPTY_VECTOR = NULL;

static PyObject* pyrsistent_pvec(PyObject *self, PyObject *args) {
    PyObject *argObj = NULL;  /* list of arguments */
    PyObject *result;
    PyObject *tempVec;

    debug("pyrsistent_pvec(): %x\n", args);

    /* the O! parses for a Python object (listObj) checked to be of type PyList_Type */
    if(!PyArg_ParseTuple(args, "|O", &argObj)) return NULL;
    
    Py_INCREF(EMPTY_VECTOR);
    result = EMPTY_VECTOR;

    if(argObj == NULL) return result; 

    debug("pyrsistent_pvec(): Arguments passed\n", args);

    PyObject *iterator = PyObject_GetIter(argObj);
    PyObject *item;

    if (iterator == NULL) {
      return NULL;
    }

    debug("pyrsistent_pvec(): Iterating\n");
    
    // TODO: More efficient version that fills up to full tail
    //       before pushing it into the vector
    while (item = PyIter_Next(iterator)) {
      tempVec = PVector_append(result, item);
      Py_DECREF(result);
      result = tempVec;
      Py_DECREF(item);
    }

    Py_DECREF(iterator);

    return result;
}

static PVector* emptyNewPvec() {
  // TODO: Support GC
  PVector *pvec = PyObject_New(PVector, &PVectorType);
  debug("pymem alloc_new %x\n", pvec);
  debug("Ref cnt: %u\n", pvec->ob_refcnt);
  pvec->count = (Py_ssize_t)0;
  pvec->dict = PyDict_New();
  pvec->shift = SHIFT;
  pvec->root = newNode();
  pvec->tail = newNode();
  return pvec;
}

static void incRefs(PyObject **obj) {
  int i;
  for(i = 0; i < BRANCH_FACTOR; i++) {
    Py_XINCREF(obj[i]);
  }
}

static PVector* newPvec(unsigned int count, unsigned int shift, VNode *root) {
  // TODO: Support GC
  PVector *pvec = PyObject_New(PVector, &PVectorType);
  debug("pymem alloc_copy %x\n", pvec);
  debug("Ref cnt: %u\n", pvec->ob_refcnt);
  pvec->count = count;
  pvec->dict = PyDict_New();
  pvec->shift = shift;
  pvec->root = root;
  pvec->tail = newNode();
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


/*
 Steals a reference to the object that is appended to the list.
 Haven't really decided if this is the right thing to do yet...
*/
static PyObject* PVector_append(PVector *self, PyObject *obj) {
  // TODO: Refactor and cleanup this function
  assert (obj != NULL);

  unsigned int tail_size = self->count - tailOff(self);
  debug("append(): count = %u, tail_size = %u\n", self->count, tail_size);

  // Does the new object fit in the tail? If so, take a copy of the tail and
  // insert the new element in that.
  if(tail_size < BRANCH_FACTOR) {
    self->root->refCount++;
    PVector *new_pvec = newPvec(self->count + 1, self->shift, self->root);
    copyInsert(new_pvec->tail->items, self->tail->items, tail_size, obj);
    incRefs(new_pvec->tail->items);
    debug("append(): new_pvec=%x, new_pvec->tail=%x, new_pvec->root=%x\n", new_pvec, new_pvec->tail, new_pvec->root);

    return new_pvec;
  }

  // Tail is full, need to push it into the tree
  
  // Is the root node full?
  VNode* new_root;
  unsigned int new_shift;
  if((self->count >> SHIFT) > (1 << self->shift)) {
    new_root = newNode();
    new_root->items[0] = self->root;
    // TODO: Is it possible to use pushTail here somehow?
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
  debug("append_push(): pvec=%x, pvec->tail=%x, pvec->root=%x\n", pvec, pvec->tail, pvec->root);
  return pvec;
}

static VNode* doAssoc(VNode* node, unsigned int level, unsigned int position, PyObject* value) {
  if(level == 0) {
    debug("doAssoc(): level == 0\n");
    VNode* theNewNode = newNode();
    copyInsert(theNewNode->items, node->items, position & BIT_MASK, value);
    incRefs(theNewNode->items);
    return theNewNode;
  } else {
    debug("doAssoc(): level == %i\n", level);
    VNode* theNewNode = copyNode(node);
    Py_ssize_t index = (position >> level) & BIT_MASK;

    // Release this node since we're about to replace it
    ((VNode*)theNewNode->items[index])->refCount--;
    theNewNode->items[index] = doAssoc(node->items[index], level - SHIFT, position, value); 
    return theNewNode;
  }
}

/*
 Steals a reference to the object that is appended to the list.
 Haven't really decided if this is the right thing to do yet...
*/
static PyObject* PVector_assoc(PVector *self, PyObject *args) {
  PyObject *argObj = NULL;  /* list of arguments */
  Py_ssize_t position;

  debug("\nassoc(): Entering\n");

  /* The n parses for size, the O parses for a Python object 
     (listObj) checked to be of type PyList_Type */
  if(!PyArg_ParseTuple(args, "nO", &position, &argObj)) return NULL;

  debug("assoc(): Arguments parsed: %d, count=%d\n", position, self->count);
    
  if((0 <= position) && (position < self->count)) {
    debug("assoc(): Position within bounds\n");
    if(position >= tailOff(self)) {
      debug("assoc(): Position in tail\n");
      self->root->refCount++;
      PVector *new_pvec = newPvec(self->count, self->shift, self->root);
      copyInsert(new_pvec->tail->items, self->tail->items, position & BIT_MASK, argObj);
      incRefs(new_pvec->tail->items);
      return new_pvec;
    } else {
      VNode *newRoot = doAssoc(self->root, self->shift, position, argObj);
      PVector *new_pvec = newPvec(self->count, self->shift, newRoot);

      // Free the tail and replace it with a reference to the tail to the original vector
      freeNode(new_pvec->tail);
      new_pvec->tail = self->tail;
      self->tail->refCount++;
      return new_pvec;
    }
  } else if (position == self->count) {
    debug("assoc(): Applying append instead\n");
    return PVector_append(self, argObj);
  } else {
    debug("assoc(): Index out of range\n");
    PyErr_SetString(PyExc_IndexError, "System command failed");
    return NULL;
  }
}


static PyMethodDef PyrsistentMethods[] = {
  {"pvec", pyrsistent_pvec, METH_VARARGS, "Factory method for persistent vectors"},
  {NULL, NULL, 0, NULL}
};

PyMODINIT_FUNC initpyrsistentc(void) {
  PyObject* m;
  
  // Only allow creation/initialization through factory method pvec
  PVectorType.tp_init = NULL;
  PVectorType.tp_new = NULL;

  // Inherit from ABC to make this type appear as a well behaved collection
  PyObject* module = PyImport_ImportModule("collections");
  PyObject* moduleDict = PyModule_GetDict(module);
  PyObject* c = PyDict_GetItemString(moduleDict, "Sequence");
  
  if(c == NULL) {
    debug("Was NULL!\n");
  }

  Py_INCREF(c);
  PVectorType.tp_base = c;
  if (PyType_Ready(&PVectorType) < 0)
    return;

  m = Py_InitModule("pyrsistentc", PyrsistentMethods);

  if (m == NULL)
    return;

  SHIFT = __builtin_popcount(BIT_MASK);
  
  debug("pymem creating empty vector\n");
  if(EMPTY_VECTOR == NULL) {
    EMPTY_VECTOR = emptyNewPvec();
  }

  Py_INCREF(&PVectorType);
  PyModule_AddObject(m, "PVector", (PyObject *)&PVectorType);
}
