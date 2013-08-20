#include <Python.h>
#include <structmember.h>
/*
TODO: 
- Python 3 compatibility?
- Inherit Sequence
*/


/*
Persistant/Immutable data structures. Unfortunately I have not been able to come
up with an implementation that is 100% immutable due to the ref counts used by
Python internally so the GIL must still be at work...

To the end user they should appear immutable at least.
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

static VNode* newNode() {
  VNode* result = malloc(sizeof(VNode));
  printf("meminfo malloc_new %x\n", result);
  memset(result, 0x0, sizeof(VNode));
  result->refCount = 1;
  nodeCount++;
  printf("newNode() Node count = %i\n", nodeCount);
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
  printf("copyNode(): Node count = %i\n", nodeCount);
  return result;
}


static void freeNode(VNode* node) {
  free(node);
  nodeCount--;
  printf("meminfo free %x\n", node);
  printf("freeNode(): Node count = %i\n", nodeCount);
}


static Py_ssize_t PVector_len(PVector *self) {
  return self->count;
}


static Py_ssize_t vec_tailoff(PVector *self) {
  if(self->count < BRANCH_FACTOR) {
    return 0;
  }
  
  return ((self->count - 1) >> SHIFT) << SHIFT;
}


static VNode* nodeFor(PVector *self, int i){
  int level;
  if((i >= 0) && (i < self->count)) {
    if(i >= vec_tailoff(self)) {
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
  if(node == NULL) {
    return;
  }

  printf("releaseNode(): node=%x, level=%i, refCount=%i\n", node, level, node->refCount);

  int i;
  if(level > 0) {
    node->refCount--;
    if(node->refCount == 0) {
      for(i = 0; i < BRANCH_FACTOR; i++) {
	if(node->items[i] != NULL) {
	  releaseNode(level - SHIFT, node->items[i]);
	}
      }
      freeNode(node);
    }
  } else {
    node->refCount--;
    if(node->refCount == 0) {
      for(i = 0; i < BRANCH_FACTOR; i++) {
	Py_XDECREF(node->items[i]);
      }
      freeNode(node);
    }
  }

  printf("releaseNode(): Done! node=%x!\n", node);
}

/*
 Returns all references to PyObjects that have been stolen. Also decrements
 the internal reference counts used for shared memory structures and deallocates
 those if needed.
*/
static void PVector_dealloc(PVector *self) {
  printf("Dealloc(): self=%x, self->count=%i, tail->refCount=%i, root->refCount=%i, self->shift=%i\n", self, self->count, self->tail->refCount, self->root->refCount, self->shift);
  printf("Dealloc(): Releasing self->tail=%x\n", self->tail);
  releaseNode(0, self->tail);
  printf("Dealloc(): Releasing self->root=%x\n", self->root);
  releaseNode(self->shift, self->root);

  printf("Dealloc(): Done!\n");
}

static void copy_insert(void** dest, void** src, Py_ssize_t pos, void *obj) {
  memcpy(dest, src, BRANCH_FACTOR * sizeof(void*));
  dest[pos] = obj;
}

static PyObject* PVector_append(PVector *self, PyObject *obj);

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
	{"append",  (PyCFunction)PVector_append,  METH_O, "Appends an element"},
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
  0,				/* tp_iter           */
  0,				/* tp_iternext       */
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
  // TODO: Support GC
  Py_INCREF(EMPTY_VECTOR);
  return EMPTY_VECTOR;
}



static PVector* emptyNewPvec() {
  // TODO: Support GC
  PVector *pvec = PyObject_New(PVector, &PVectorType);
  printf("Ref cnt: %u\n", pvec->ob_refcnt);
  pvec->count = (Py_ssize_t)0;
  pvec->dict = PyDict_New();
  pvec->shift = SHIFT;
  pvec->root = newNode();
  pvec->tail = newNode();
  return pvec;
}


/*
    def append(self, val):
        #room in tail?
        if((self.cnt - self._tailoff()) < BRANCH_FACTOR):
            new_tail = list(self.tail)
            new_tail.append(val)
            return PVector(self.cnt + 1, self.shift, self.root, new_tail)
        
        # Full tail, push into tree
        new_shift = self.shift
        # Overflow root?
        if((self.cnt >> SHIFT) > (1 << self.shift)): # >>>
            new_root = [self.root, self.new_path(self.shift, self.tail)]
            new_shift += SHIFT
         else:
            new_root = self.push_tail(self.shift, self.root, self.tail)
    
        return PVector(self.cnt + 1, new_shift, new_root, [val])
*/


static void incRefs(PyObject **obj) {
  int i;
  for(i = 0; i < BRANCH_FACTOR; i++) {
    Py_XINCREF(obj[i]);
  }
}

static PVector* newPvec(unsigned int count, unsigned int shift, VNode *root) {
  // TODO: Support GC
  PVector *pvec = PyObject_New(PVector, &PVectorType);
  printf("Ref cnt: %u\n", pvec->ob_refcnt);
  pvec->count = count;
  pvec->dict = PyDict_New();
  pvec->shift = shift;
  pvec->root = root;
  pvec->tail = newNode();
  return pvec;
}

static VNode* newPath(unsigned int level, VNode* node){
  if(level == 0) {
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
  printf("pushTail(): count = %i, sub_index = %i\n", count, sub_index);

  if(level == SHIFT) {
    // We're at the bottom
    tail->refCount++;
    nodeToInsert = tail;
  } else {
    // More levels available in the tree
    child = parent->items[sub_index];
    nodeToInsert = (child != NULL) ?
      pushTail(level - SHIFT, count, child, tail) :
      newPath(level - SHIFT, tail);
  }
  
  result->items[sub_index] = nodeToInsert;
  return result;
}


/*
 Steals a reference to the object that is appended to the list.
 Haven't really decided if this is the right thing to do yet...
*/
static PyObject* PVector_append(PVector *self, PyObject *obj) {
  assert (obj != NULL);

  unsigned int tail_size = self->count - vec_tailoff(self);
  printf("append(): count = %u, tail_size = %u\n", self->count, tail_size);

  // Does the new object fit in the tail? If so, take a copy of the tail and
  // insert the new element in that.
  if(tail_size < BRANCH_FACTOR) {
    self->root->refCount++;
    PVector *new_pvec = newPvec(self->count + 1, self->shift, self->root);
    copy_insert(new_pvec->tail->items, self->tail->items, tail_size, obj);
    incRefs(new_pvec->tail->items);
    //    new_pvec->count = self->count + 1;
    printf("append(): new_pvec=%x, new_pvec->tail=%x, new_pvec->root=%x\n", new_pvec, new_pvec->tail, new_pvec->root);

    return new_pvec;
  }

  // Tail is full, need to push it into the tree
  //  if((self->count >> SHIFT) > (1 < self->SHIFT))
  // TODO: Is the root full?
  unsigned int new_shift = self->shift;
  VNode* new_root = pushTail(self->shift, self->count, self->root, self->tail);
  //  self->tail->refCount++;
  PVector* pvec = newPvec(self->count + 1, new_shift, new_root);
  pvec->tail->items[0] = obj;
  Py_XINCREF(obj);
  printf("append_push(): pvec=%x, pvec->tail=%x, pvec->root=%x\n", pvec, pvec->tail, pvec->root);
  return pvec;
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
    printf("Was NULL!\n");
  }

  Py_INCREF(c);
  PVectorType.tp_base = c;
  if (PyType_Ready(&PVectorType) < 0)
    return;

  m = Py_InitModule("pyrsistentc", PyrsistentMethods);

  if (m == NULL)
    return;

  SHIFT = __builtin_popcount(BIT_MASK);

  if(EMPTY_VECTOR == NULL) {
    EMPTY_VECTOR = emptyNewPvec();
  }

  Py_INCREF(&PVectorType);
  PyModule_AddObject(m, "PVector", (PyObject *)&PVectorType);
}


/*
1 - Full support for insert and direct access
2 - Proper reference counting for these cases

TODO:
- Accessor function
- Reference counting
- Factory method for vector
- Inherit abstract sequence class
- Tests
- Code clean up
*/
