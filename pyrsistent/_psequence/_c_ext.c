// #define PYMALLOC_DEBUG 1

#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <structmember.h>

#include <stdarg.h>
#include <stdbool.h>
#include <assert.h>

/*
Persistent/Immutable/Functional sequence and helper types.

Please note that they are anything but immutable at this level since
there is a whole lot of reference counting going on. That's the way
CPython works though and the GIL makes them appear immutable.

To the programmer using them from Python they appear immutable and
behave immutably at least.

Naming conventions
------------------
pyrsistent_* - Methods part of the interface
<typename>_* - Instance methods of types. For examle FTree_extend(...)
F<typename>  - FingerTree related types, considered private
P<typename>  - PSequence related types, considered public

All other methods are camel cased without prefix. All methods are static,
none should require to be exposed outside of this module.
*/

// {{{ typedef

typedef struct FNode {
	size_t refs;
	size_t size;
	union {
		PyObject* value;
		struct FNode* items[3];
	};
} FNode;

typedef struct FDigit {
	size_t refs;
	size_t size;
	int  count;
	FNode* items[4];
} FDigit;

typedef struct FTree FTree;

typedef struct FDeep {
	size_t size;
	FDigit* left;
	FTree* middle;
	FDigit* right;
} FDeep;

typedef enum FTreeT {
	FEmptyT  = 0,
	FSingleT = 1,
	FDeepT   = 2
} FTreeT ;

typedef struct FTree {
	size_t refs;
	FTreeT type;
	union {
		void* empty;
		FNode* single;
		FDeep* deep;
	};
} FTree;

typedef struct FView {
	FNode* node;
	FTree* tree;
} FView;

typedef struct FSplit {
	FTree* left;
	FNode* node;
	FTree* right;
} FSplit;

typedef struct FIndex {
	size_t index;
	union {
		FNode* node;
		PyObject* value;
	};
} FIndex;

typedef struct FIndex2 {
	size_t index1;
	size_t index2;
	union {
		FNode* node;
		PyObject* value;
	};
} FIndex2;

typedef struct FInsert {
	FNode* extra;
	union {
		FNode* node;
		FDigit* digit;
	};
} FInsert;

typedef struct FMeld {
	bool full;
	union {
		FNode* node;
		FDigit* digit;
		FTree* tree;
	};
} FMeld;

typedef struct FMerge {
	union {
		FNode* left;
		FNode* node;
	};
	union {
		FNode* right;
		void* extra;
	};
} FMerge;

typedef enum FIterT {
	FTreeI  = 0,
	FDigitI = 1,
	FNodeI  = 2
} FIterT;

typedef struct FIter {
	FIterT type;
	int index;
	union {
		FTree* tree;
		FNode* node;
		FDigit* digit;
	};
	struct FIter* next;
} FIter;

typedef struct FMset {
	size_t index;
	size_t count;
	FIndex2* items;
} FMset;

typedef struct FSlice {
	size_t modulo;
	size_t count;
	size_t step;
	union {
		PyObject** input;
		FNode** output;
	};
} FSlice;

typedef struct PSequence {
	PyObject_HEAD
	FTree* tree;
	PyObject* weakrefs;
} PSequence;

typedef struct PSequenceIter {
	PyObject_HEAD
	Py_ssize_t index;
	bool reverse;
	PSequence* seq;
	FIter* stack;
} PSequenceIter;

typedef struct PSequenceEvolver {
	PyObject_HEAD
	PSequence* seq;
} PSequenceEvolver;

static PyTypeObject PSequenceType;
static PyTypeObject PSequenceIterType;
static PyTypeObject PSequenceEvolverType;

// }}}

// {{{ misc

#if defined(__GNUC__) || defined(__clang__)
# define UNUSED __attribute__((unused))
#else
# define UNUSED
#endif

static PSequence* EMPTY_SEQUENCE = NULL;
static FTree EMPTY_TREE = { .refs = 1, .type = FEmptyT, .empty = NULL };

static void* PSequence_indexError(Py_ssize_t index) {
	return PyErr_Format(PyExc_IndexError, "index out of range: %zd", index);
}

static int FNode_count(const FNode* node) {
	if(node->size == 1)
		return 1;
	if(node->items[2] == NULL)
		return 2;
	else
		return 3;
}

UNUSED static size_t FNode_depth(const FNode* node) {
	assert(node != NULL);
	size_t n = 0;
	while(node->size != 1) {
		++n;
		node = node->items[0];
		assert(node != NULL);
	}
	return n;
}

static size_t FTree_size(const FTree* tree) {
	switch(tree->type) {
		case FEmptyT:  return 0;
		case FSingleT: return tree->single->size;
		case FDeepT:   return tree->deep->size;
		default: Py_UNREACHABLE();
	}
}

static Py_ssize_t FTree_ssize(const FTree* tree) {
	return (Py_ssize_t)FTree_size(tree);
}

static bool FTree_empty(const FTree* tree) {
	return tree->type == FEmptyT;
}

static bool FTree_checkIndex(const FTree* tree, Py_ssize_t* index) {
	Py_ssize_t size = FTree_size(tree);
	Py_ssize_t idx = *index;
	if(idx < 0) idx += size;
	if(!(0 <= idx && idx < size))
		return false;
	*index = idx;
	return true;
}

static int FIndex2_compare(const FIndex2* x, const FIndex2* y) {
	if(x->index1 == y->index1)
		return x->index2 - y->index2;
	return x->index1 - y->index1;
}

// }}}

// {{{ print
// for debugging tree structures

#ifndef NDEBUG

UNUSED static void FIndent_print(int indent) {
	// printf("%d ", indent);
	for(int i = 0; i < indent; ++i)
		printf("  ");
}

UNUSED static void FNode_print(FNode* node, int indent) {
	FIndent_print(indent);
	if(node->size == 1) {
		printf("FElement(refs=%zu) ", node->refs);
		PyObject_Print(node->value, stdout, 0);
		// printf("%p(refs=%zd)", node->value, Py_REFCNT(node->items[0]));
		printf("\n");
	} else {
		printf("FNode[size=%zu](refs=%zu)\n", node->size, node->refs);
		FNode_print((FNode*)node->items[0], indent + 1);
		FNode_print((FNode*)node->items[1], indent + 1);
		if(node->items[2] != NULL)
			FNode_print((FNode*)node->items[2], indent + 1);
	}
}

UNUSED static void FDigit_print(FDigit* digit, int indent) {
	FIndent_print(indent);
	printf("FDigit[size=%zu](refs=%zu)\n", digit->size, digit->refs);
	for(int i = 0; i < digit->count; ++i)
		FNode_print(digit->items[i], indent + 1);
}

UNUSED static void FTree_print(FTree* tree, int indent) {
	FIndent_print(indent);
	switch(tree->type) {
		case FEmptyT:
			printf("FEmpty(refs=%zu)\n", tree->refs);
			break;
		case FSingleT:
			printf("FSingle(refs=%zu)\n", tree->refs);
			FNode_print(tree->single, indent + 1);
			break;
		case FDeepT:
			printf("FDeep[size=%zu](refs=%zu)\n",
				tree->deep->size, tree->refs);
			FDigit_print(tree->deep->left, indent + 1);
			FTree_print(tree->deep->middle, indent + 1);
			FDigit_print(tree->deep->right, indent + 1);
			break;
		default: Py_UNREACHABLE();
	}
}

UNUSED static void FIter_print(FIter* iter) {
	while(iter != NULL) {
		switch(iter->type) {
			case FTreeI: printf("Tree"); break;
			case FNodeI: printf("Node"); break;
			case FDigitI: printf("Digit"); break;
			default: Py_UNREACHABLE();
		}
		printf("%d ", iter->index);
		iter = iter->next;
	}
	printf("(nil)\n");
}

#endif

// }}}

// {{{ debug

typedef enum FRefs {
	FTreeR = 0,
	FDigitR = 1,
	FNodeR = 2,
} FRefs;

#ifndef NDEBUG
static long FRefs_count[3];
static long FRefs_get(FRefs type) { return FRefs_count[type]; }
static void FRefs_inc(FRefs type) { ++FRefs_count[type]; }
static void FRefs_dec(FRefs type) { --FRefs_count[type]; }
#else
#define FRefs_get(type) 0
#define FRefs_inc(type)
#define FRefs_dec(type)
#endif

// }}}

// {{{ ref count

static void* PObj_IncRef(void* obj) {
	Py_INCREF(obj);
	return obj;
}

static FNode* FNode_incRef(FNode* node) {
	assert(node != NULL);
	++node->refs;
	FRefs_inc(FNodeR);
	return node;
}

static FNode* FNode_incRefM(FNode* node) {
	if(node != NULL) {
		++node->refs;
		FRefs_inc(FNodeR);
	}
	return node;
}

static void FNode_decRef(FNode* node) {
	assert(node != NULL);
	assert(node->refs > 0);
	FRefs_dec(FNodeR);
	if(--node->refs == 0) {
		if(node->size != 1) {
			FNode_decRef(node->items[0]);
			FNode_decRef(node->items[1]);
			if(node->items[2] != NULL)
				FNode_decRef(node->items[2]);
		} else Py_DECREF(node->value);
		PyMem_Free(node);
	}
}

static void* FNode_decRefRet(FNode* node, void* ret) {
	FNode_decRef(node);
	return ret;
}

static FDigit* FDigit_incRef(FDigit* digit) {
	if(digit != NULL) {
		++digit->refs;
		FRefs_inc(FDigitR);
	}
	return digit;
}

static void FDigit_decRef(FDigit* digit) {
	assert(digit != NULL);
	assert(digit->refs > 0);
	FRefs_dec(FDigitR);
	if(--digit->refs == 0) {
		switch(digit->count) {
			case 4: FNode_decRef(digit->items[3]);
			case 3: FNode_decRef(digit->items[2]);
			case 2: FNode_decRef(digit->items[1]);
			case 1: FNode_decRef(digit->items[0]);
				break;
			default: Py_UNREACHABLE();
		}
		PyMem_Free(digit);
	}
}

// static void* FDigit_decRefRet(FDigit* digit, void* ret) {
	// FDigit_decRef(digit);
	// return ret;
// }

static FTree* FTree_incRef(FTree* tree) {
	if(tree != NULL) {
		++tree->refs;
		FRefs_inc(FTreeR);
	}
	return tree;
}

static void FTree_decRef(FTree* tree) {
	assert(tree != NULL);
	assert(tree->refs > 0);
	FRefs_dec(FTreeR);
	if(--tree->refs == 0) {
		switch(tree->type) {
			case FEmptyT:
				break;
			case FSingleT:
				FNode_decRef(tree->single);
				break;
			case FDeepT:
				FDigit_decRef(tree->deep->left);
				FTree_decRef(tree->deep->middle);
				FDigit_decRef(tree->deep->right);
				PyMem_Free(tree->deep);
				break;
			default: Py_UNREACHABLE();
		}
		PyMem_Free(tree);
	}
}

static void* FTree_decRefRet(FTree* tree, void* ret) {
	FTree_decRef(tree);
	return ret;
}

static FIter* FIter_incRef(FIter* iter) {
	switch(iter->type) {
		case FTreeI: FTree_incRef(iter->tree); break;
		case FDigitI: FDigit_incRef(iter->digit); break;
		case FNodeI: FNode_incRef(iter->node); break;
		default: Py_UNREACHABLE();
	}
	return iter;
}

static FIter* FIter_decRef(FIter* iter) {
	switch(iter->type) {
		case FTreeI: FTree_decRef(iter->tree); break;
		case FDigitI: FDigit_decRef(iter->digit); break;
		case FNodeI: FNode_decRef(iter->node); break;
		default: Py_UNREACHABLE();
	}
	return iter;
}

// }}}

// {{{ constructor

// {{{ FNode

static FNode* FNode_alloc() {
	FNode* node = PyMem_Malloc(sizeof(FNode));
	node->refs = 1;
	FRefs_inc(FNodeR);
	return node;
}

static FNode* FNode_make(
	const size_t size,
	const FNode* n0,
	const FNode* n1,
	const FNode* n2
) {
	assert(size == 1 || size == n0->size + n1->size + (n2 ? n2->size : 0));
	FNode* node = FNode_alloc();
	node->size = size;
	node->items[0] = (FNode*)n0; assert(size == 1 || n0 != NULL);
	node->items[1] = (FNode*)n1; assert(size == 1 || n1 != NULL);
	node->items[2] = (FNode*)n2;
	return node;
}

static FNode* FNode_makeS(
	const FNode* n0,
	const FNode* n1,
	const FNode* n2
) {
	assert(n0 != NULL); assert(n1 != NULL);
	size_t size = n0->size + n1->size + (n2 == NULL ? 0 : n2->size);
	return FNode_make(size, n0, n1, n2);
}

static FNode* FNode_makeNS(const int count, FNode** nodes) {
	switch(count) {
		case 2: return FNode_make(
			nodes[0]->size + nodes[1]->size,
			nodes[0], nodes[1], NULL);
		case 3: return FNode_make(
			nodes[0]->size + nodes[1]->size + nodes[2]->size,
			nodes[0], nodes[1], nodes[2]);
		default: Py_UNREACHABLE();
	}
}

static FNode* FNode_makeE(const PyObject* item) {
	return FNode_make(1, (FNode*)item, NULL, NULL);
}

// }}}

// {{{ FDigit

static FDigit* FDigit_alloc() {
	FDigit* digit = PyMem_Malloc(sizeof(FDigit));
	digit->refs = 1;
	FRefs_inc(FDigitR);
	return digit;
}

static FDigit* FDigit_make(
	const size_t size,
	const int count,
	const FNode* n0,
	const FNode* n1,
	const FNode* n2,
	const FNode* n3
) {
	assert(1 <= count && count <= 4);
	FDigit* digit = FDigit_alloc();
	digit->size = size;
	digit->count = count;
	digit->items[0] = (FNode*)n0; assert(n0 != NULL);
	digit->items[1] = (FNode*)n1; assert((count < 2) == (n1 == NULL));
	digit->items[2] = (FNode*)n2; assert((count < 3) == (n2 == NULL));
	digit->items[3] = (FNode*)n3; assert((count < 4) == (n3 == NULL));
	return digit;
}

static FDigit* FDigit_makeN(
	const size_t size,
	const int count,
	FNode** nodes
) {
	switch(count) {
		case 1: return FDigit_make(size,
			count, nodes[0], NULL, NULL, NULL);
		case 2: return FDigit_make(size,
			count, nodes[0], nodes[1], NULL, NULL);
		case 3: return FDigit_make(size,
			count, nodes[0], nodes[1], nodes[2], NULL);
		case 4: return FDigit_make(size,
			count, nodes[0], nodes[1], nodes[2], nodes[3]);
		default: Py_UNREACHABLE();
	}
}

static FDigit* FDigit_makeS(
	const int count,
	const FNode* n0,
	const FNode* n1,
	const FNode* n2,
	const FNode* n3
) {
	assert(1 <= count && count <= 4);
	FDigit* digit = FDigit_alloc();
	digit->count = count;
	digit->items[0] = (FNode*)n0; assert(n0 != NULL);
	digit->items[1] = (FNode*)n1; assert((count < 2) == (n1 == NULL));
	digit->items[2] = (FNode*)n2; assert((count < 3) == (n2 == NULL));
	digit->items[3] = (FNode*)n3; assert((count < 4) == (n3 == NULL));
	size_t size = n0->size;
	switch(count) {
		case 4: assert(n3 != NULL); size += n3->size;
		case 3: assert(n2 != NULL); size += n2->size;
		case 2: assert(n1 != NULL); size += n1->size;
		case 1: break;
		default: Py_UNREACHABLE();
	}
	digit->size = size;
	return digit;
}

static FDigit* FDigit_makeNS(const int count, FNode** nodes) {
	assert(nodes[0] != NULL);
	size_t size = nodes[0]->size;
	switch(count) {
		case 4: assert(nodes[3] != NULL); size += nodes[3]->size;
		case 3: assert(nodes[2] != NULL); size += nodes[2]->size;
		case 2: assert(nodes[1] != NULL); size += nodes[1]->size;
		case 1: break;
		default: Py_UNREACHABLE();
	}
	return FDigit_makeN(size, count, nodes);
}

static FDigit* FDigit_fromNode(const FNode* node) {
	return FDigit_make(node->size, FNode_count(node),
		FNode_incRef(node->items[0]),
		FNode_incRef(node->items[1]),
		FNode_incRefM(node->items[2]), NULL);
}

static FDigit* FDigit_fromMerge(FMerge merge) {
	if(merge.extra == NULL)
		return FDigit_make(merge.left->size, 1,
			merge.left, NULL, NULL, NULL);
	return FDigit_make(merge.left->size + merge.right->size, 2,
		merge.left, merge.right, NULL, NULL);
}

// }}}

// {{{ FTree

static FTree* FTree_alloc() {
	FTree* tree = PyMem_Malloc(sizeof(FTree));
	tree->refs = 1;
	FRefs_inc(FTreeR);
	return tree;
}

static FTree* FEmpty_make() {
	FTree_incRef(&EMPTY_TREE);
	return &EMPTY_TREE;
}

static FTree* FSingle_make(const FNode* node) {
	FTree* tree = FTree_alloc();
	tree->type = FSingleT;
	tree->single = (FNode*)node;
	return tree;
}

static FDeep* FDeep_alloc() {
	FDeep* deep = PyMem_Malloc(sizeof(FDeep));
	return deep;
}

static FTree* FDeep_make(
	const size_t size,
	const FDigit* left,
	const FTree* middle,
	const FDigit* right
) {
	assert(size == left->size + FTree_size(middle) + right->size);
	FDeep* deep = FDeep_alloc();
	deep->size = size;
	deep->left = (FDigit*)left;
	deep->middle = (FTree*)middle;
	deep->right = (FDigit*)right;
	FTree* tree = FTree_alloc();
	tree->type = FDeepT;
	tree->deep = deep;
	return tree;
}

static FTree* FDeep_makeS(
	const FDigit* left,
	const FTree* middle,
	const FDigit* right
) {
	size_t size = left->size + FTree_size(middle) + right->size;
	return FDeep_make(size, left, middle, right);
}

static FTree* FTree_fromDigit(const FDigit* digit) {
	switch(digit->count) {
		case 1: return FSingle_make(FNode_incRef(digit->items[0]));
		case 2: return FDeep_make(digit->size,
			FDigit_make(digit->items[0]->size, 1,
				FNode_incRef(digit->items[0]), NULL, NULL, NULL),
			FEmpty_make(),
			FDigit_make(digit->items[1]->size, 1,
				FNode_incRef(digit->items[1]), NULL, NULL, NULL));
		case 3: return FDeep_make(digit->size,
			FDigit_make(digit->items[0]->size + digit->items[1]->size, 2,
				FNode_incRef(digit->items[0]),
				FNode_incRef(digit->items[1]), NULL, NULL),
				FEmpty_make(),
			FDigit_make(digit->items[2]->size, 1,
				FNode_incRef(digit->items[2]), NULL, NULL, NULL));
		case 4: return FDeep_make(digit->size,
			FDigit_make(digit->items[0]->size + digit->items[1]->size, 2,
				FNode_incRef(digit->items[0]),
				FNode_incRef(digit->items[1]), NULL, NULL),
				FEmpty_make(),
			FDigit_make(digit->items[2]->size + digit->items[3]->size, 2,
				FNode_incRef(digit->items[2]),
				FNode_incRef(digit->items[3]), NULL, NULL));
		default: Py_UNREACHABLE();
	}
}

static FTree* FTree_fromMerge(FMerge merge) {
	if(merge.extra == NULL)
		return FSingle_make(merge.left);
	return FDeep_makeS(
		FDigit_make(merge.left->size, 1, merge.left, NULL, NULL, NULL),
		FEmpty_make(),
		FDigit_make(merge.right->size, 1, merge.right, NULL, NULL, NULL));
}

// }}}

// {{{ PSequence

static PSequence* PSequence_make(const FTree* tree) {
	assert(tree != NULL);
	PSequence* seq = PyObject_GC_New(PSequence, &PSequenceType);
	seq->tree = (FTree*)tree;
	seq->weakrefs = NULL;
	PyObject_GC_Track(seq);
	return seq;
}

static void PSequence_dealloc(PSequence* self) {
	if (self->weakrefs != NULL)
		PyObject_ClearWeakRefs((PyObject*)self);
	PyObject_GC_UnTrack(self);
	Py_TRASHCAN_SAFE_BEGIN(self);
	FTree_decRef(self->tree);
	PyObject_GC_Del(self);
	Py_TRASHCAN_SAFE_END(self);
}

// }}}

// {{{ FIter

static inline FIter* FIter_alloc() {
	return PyMem_Malloc(sizeof(FIter));
}

static inline FIter* FIter_make(
	FIterT type,
	int index,
	void* item,
	FIter* next
) {
	FIter* iter = FIter_alloc();
	iter->type = type;
	iter->index = index;
	iter->tree = item;
	iter->next = next;
	FIter_incRef(iter);
	return iter;
}

static void FIter_dealloc(FIter* iter, bool all) {
	if(iter == NULL) return;
	FIter_decRef(iter);
	FIter* next = iter->next;
	PyMem_Free(iter);
	if(all) FIter_dealloc(next, all);
}

// }}}

// {{{ PSequenceIter

static PSequenceIter* PSequenceIter_make(
	Py_ssize_t index,
	bool reverse,
	PSequence* seq,
	FIter* stack
) {
	PSequenceIter* iter = PyObject_GC_New(PSequenceIter, &PSequenceIterType);
	iter->index = index;
	iter->reverse = reverse;
	iter->seq = seq;
	iter->stack = stack;
	PyObject_GC_Track(iter);
	return iter;
}

static void PSequenceIter_dealloc(PSequenceIter* self) {
	PyObject_GC_UnTrack(self);
	Py_DECREF(self->seq);
	FIter_dealloc(self->stack, true);
	PyObject_GC_Del(self);
}

// }}}

// {{{ PSequenceEvolver

static PSequenceEvolver* PSequenceEvolver_make(PSequence* seq) {
	assert(seq != NULL);
	PSequenceEvolver* evo = PyObject_GC_New(
		PSequenceEvolver, &PSequenceEvolverType);
	evo->seq = seq;
	PyObject_GC_Track(evo);
	return evo;
}

static void PSequenceEvolver_dealloc(PSequenceEvolver* self) {
	PyObject_GC_UnTrack(self);
	Py_TRASHCAN_SAFE_BEGIN(self);
	Py_DECREF(self->seq);
	PyObject_GC_Del(self);
	Py_TRASHCAN_SAFE_END(self);
}

// }}}

// {{{ misc

static inline FView FView_make(FNode* node, FTree* tree) {
	FView view = { .node=node, .tree=tree };
	return view;
}

static inline FSplit FSplit_make(FTree* left, FNode* node, FTree* right) {
	FSplit split = { .left=left, .node=node, .right=right };
	return split;
}

static inline FIndex FIndex_make(size_t idx, FNode* node) {
	FIndex index = { .index=idx, .node=node };
	return index;
}

static inline FIndex2 FIndex2_make(size_t idx1, size_t idx2, FNode* node) {
	FIndex2 index = { .index1=idx1, .index2=idx2, .node=node };
	return index;
}

static inline FInsert FInsert_make(FNode* extra, void* value) {
	FInsert insert = { .extra=extra, .node=value };
	return insert;
}

static inline FMeld FMeld_make(bool full, void* value) {
	FMeld meld = { .full=full, .node=value };
	return meld;
}

static inline FMerge FMerge_make(FNode* left, FNode* right) {
	FMerge merge = { .left=left, .right=right };
	return merge;
}

// }}}

// }}}

// {{{ toTree

static PyObject* FNode_toTree(const FNode* node) {
	assert(node != NULL);
	if(node->size == 1)
		return Py_BuildValue("(slO)",
			"Node", (long)node->size,  node->value);
	if(FNode_count(node) == 2)
		return Py_BuildValue("(slNN)",
			"Node", (long)node->size,
			FNode_toTree(node->items[0]),
			FNode_toTree(node->items[1]));
	return Py_BuildValue("(slNNN)",
		"Node", (long)node->size,
		FNode_toTree(node->items[0]),
		FNode_toTree(node->items[1]),
		FNode_toTree(node->items[2]));
}

static PyObject* FDigit_toTree(const FDigit* digit) {
	assert(digit != NULL);
	switch(digit->count) {
		case 1:
			return Py_BuildValue("(slN)",
				"Digit", (long)digit->size,
				FNode_toTree(digit->items[0]));
		case 2:
			return Py_BuildValue("(slNN)",
				"Digit", (long)digit->size,
				FNode_toTree(digit->items[0]),
				FNode_toTree(digit->items[1]));
		case 3:
			return Py_BuildValue("(slNNN)",
				"Digit", (long)digit->size,
				FNode_toTree(digit->items[0]),
				FNode_toTree(digit->items[1]),
				FNode_toTree(digit->items[2]));
		case 4:
			return Py_BuildValue("(slNNNN)",
				"Digit", (long)digit->size,
				FNode_toTree(digit->items[0]),
				FNode_toTree(digit->items[1]),
				FNode_toTree(digit->items[2]),
				FNode_toTree(digit->items[3]));
		default: Py_UNREACHABLE();
	}
}

static PyObject* FTree_toTree(const FTree* tree) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return Py_BuildValue("(sl)", "Tree", 0);
		case FSingleT: return Py_BuildValue("(slN)",
			"Tree", (long)FTree_size(tree),
			FNode_toTree(tree->single));
		case FDeepT: return Py_BuildValue("(slNNN)",
			"Tree", (long)FTree_size(tree),
			FDigit_toTree(tree->deep->left),
			FTree_toTree(tree->deep->middle),
			FDigit_toTree(tree->deep->right));
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_toTree(PSequence* self) {
	return FTree_toTree(self->tree);
}

// }}}

// {{{ fromTuple

static bool FTuple_checkType(PyObject* arg, const char* name) {
	if(!PyTuple_Check(arg)) return PyErr_Format(
		PyExc_TypeError, "expected tuple");
	Py_ssize_t argc = PyTuple_GET_SIZE(arg);
	if(argc < 2) return PyErr_Format(
		PyExc_ValueError, "expected 2 or more items but got %zd", argc);
	PyObject* arg0 = PyTuple_GET_ITEM(arg, 0);
	int str = PyUnicode_CompareWithASCIIString(arg0, name);
	if(str != 0) return PyErr_Format(
		PyExc_AssertionError, "expected '%s' but got %R", name, arg0);
	return true;
}

static FNode* FNode_fromTuple(PyObject* arg) {
	if(!FTuple_checkType(arg, "Node")) return NULL;
	switch(PyTuple_GET_SIZE(arg)) {
		case 3: return FNode_makeE(PObj_IncRef(PyTuple_GET_ITEM(arg, 2)));
		case 4: case 5: {
			int count = 0;
			FNode* nodes[4];
			for(int i = 2; i < PyTuple_GET_SIZE(arg); ++i, ++count) {
				nodes[count] = FNode_fromTuple(PyTuple_GET_ITEM(arg, i));
				if(nodes[count] == NULL) {
					for(int k = 0; k < count; ++k)
						FNode_decRef(nodes[k]);
					return NULL;
				}
			}
			return FNode_makeNS(count, nodes);
		} default: PyErr_Format(PyExc_ValueError,
			"expected 3, 4, or 5 items but got %zd", PyTuple_GET_SIZE(arg));
			return NULL;
	}
}

static FDigit* FDigit_fromTuple(PyObject* arg) {
	if(!FTuple_checkType(arg, "Digit")) return NULL;
	int argc = PyTuple_GET_SIZE(arg);
	switch(argc) {
		case 3: case 4: case 5: case 6: {
			int count = 0;
			FNode* nodes[4];
			for(int i = 2; i < PyTuple_GET_SIZE(arg); ++i, ++count) {
				nodes[count] = FNode_fromTuple(PyTuple_GET_ITEM(arg, i));
				if(nodes[count] == NULL) {
					for(int k = 0; k < count; ++k)
						FNode_decRef(nodes[k]);
					return NULL;
				}
			}
			return FDigit_makeNS(count, nodes);
		} default: PyErr_Format(PyExc_ValueError,
			"expected 3, 4, 5, or 6 items but got %zd", PyTuple_GET_SIZE(arg));
			return NULL;
	}
}

static FTree* FTree_fromTuple(PyObject* arg) {
	if(!FTuple_checkType(arg, "Tree")) return NULL;
	switch(PyTuple_GET_SIZE(arg)) {
		case 2: return FEmpty_make();
		case 3: {
			FNode* node = FNode_fromTuple(PyTuple_GET_ITEM(arg, 2));
			if(node == NULL) return NULL;
			return FSingle_make(node);
		} case 5: {
			FDigit* left = FDigit_fromTuple(PyTuple_GET_ITEM(arg, 2));
			if(left == NULL) return NULL;
			FDigit* right = FDigit_fromTuple(PyTuple_GET_ITEM(arg, 4));
			if(right == NULL) { Py_DECREF(left); return NULL; }
			FTree* middle = FTree_fromTuple(PyTuple_GET_ITEM(arg, 3));
			if(middle == NULL) { Py_DECREF(left); Py_DECREF(right);
				return NULL; }
			return FDeep_makeS(left, middle, right);
		} default: PyErr_Format(PyExc_ValueError,
			"expected 2, 3, or 5 items but got %zd", PyTuple_GET_SIZE(arg));
			return NULL;
	}
}

static PSequence* PSequence_fromTuple(void* _, PyObject* arg) {
	FTree* tree = FTree_fromTuple(arg);
	if(tree == NULL) return NULL;
	return PSequence_make(tree);
}

// }}}

// {{{ appendLeft

static FDigit* FDigit_appendLeft(FDigit* digit, FNode* node) {
	assert(digit->count < 4);
	switch(digit->count) {
		case 3: return FDigit_make(digit->size + node->size, 4, node,
			FNode_incRef(digit->items[0]),
			FNode_incRef(digit->items[1]),
			FNode_incRef(digit->items[2]));
		case 2: return FDigit_make(digit->size + node->size, 3, node,
			FNode_incRef(digit->items[0]),
			FNode_incRef(digit->items[1]), NULL);
		case 1: return FDigit_make(digit->size + node->size, 2, node,
			FNode_incRef(digit->items[0]), NULL, NULL);
		default: Py_UNREACHABLE();
	}
}

static FTree* FTree_appendLeft(FTree* tree, FNode* node) {
	switch(tree->type) {
		case FEmptyT:
			return FSingle_make(node);
		case FSingleT:
			return FDeep_make(tree->single->size + node->size,
				FDigit_make(node->size, 1, node, NULL, NULL, NULL),
				FEmpty_make(),
				FDigit_make(tree->single->size, 1,
					FNode_incRef(tree->single), NULL, NULL, NULL));
		case FDeepT:
			if(tree->deep->left->count < 4)
				return FDeep_make(tree->deep->size + node->size,
					FDigit_appendLeft(tree->deep->left, node),
					FTree_incRef(tree->deep->middle),
					FDigit_incRef(tree->deep->right));
			return FDeep_make(tree->deep->size + node->size,
				FDigit_make(tree->deep->left->items[0]->size + node->size, 2,
					node, FNode_incRef(tree->deep->left->items[0]), NULL, NULL),
				FTree_appendLeft(tree->deep->middle, FNode_make(
					tree->deep->left->size - tree->deep->left->items[0]->size,
					FNode_incRef(tree->deep->left->items[1]),
					FNode_incRef(tree->deep->left->items[2]),
					FNode_incRef(tree->deep->left->items[3]))),
				FDigit_incRef(tree->deep->right));
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_appendLeft(PSequence* self, PyObject* value) {
	return PSequence_make(FTree_appendLeft(self->tree,
		FNode_makeE(PObj_IncRef(value))));
}

// }}}

// {{{ appendRight

static FDigit* FDigit_appendRight(FDigit* digit, FNode* node) {
	assert(digit->count < 4);
	switch(digit->count) {
		case 3: return FDigit_make(digit->size + node->size, 4,
			FNode_incRef(digit->items[0]),
			FNode_incRef(digit->items[1]),
			FNode_incRef(digit->items[2]),
			node);
		case 2: return FDigit_make(digit->size + node->size, 3,
			FNode_incRef(digit->items[0]),
			FNode_incRef(digit->items[1]),
			node, NULL);
		case 1: return FDigit_make(digit->size + node->size, 2,
			FNode_incRef(digit->items[0]),
			node, NULL, NULL);
		default: Py_UNREACHABLE();
	}
}

static FTree* FTree_appendRight(FTree* tree, FNode* node) {
	switch(tree->type) {
		case FEmptyT:
			return FSingle_make(node);
		case FSingleT:
			return FDeep_make(tree->single->size + node->size,
				FDigit_make(tree->single->size, 1,
					FNode_incRef(tree->single), NULL, NULL, NULL),
				FEmpty_make(),
				FDigit_make(node->size, 1, node, NULL, NULL, NULL));
		case FDeepT:
			if(tree->deep->right->count < 4)
				return FDeep_make(tree->deep->size + node->size,
					FDigit_incRef(tree->deep->left),
					FTree_incRef(tree->deep->middle),
					FDigit_appendRight(tree->deep->right, node));
			return FDeep_make(tree->deep->size + node->size,
				FDigit_incRef(tree->deep->left),
				FTree_appendRight(tree->deep->middle, FNode_make(
					tree->deep->right->size - tree->deep->right->items[3]->size,
					FNode_incRef(tree->deep->right->items[0]),
					FNode_incRef(tree->deep->right->items[1]),
					FNode_incRef(tree->deep->right->items[2]))),
				FDigit_make(tree->deep->right->items[3]->size + node->size,
					2, FNode_incRef(tree->deep->right->items[3]),
					node, NULL, NULL));
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_appendRight(PSequence* self, PyObject* value) {
	return PSequence_make(
		FTree_appendRight(self->tree,
			FNode_makeE(PObj_IncRef(value))));
}

// }}}

// {{{ viewLeft

static FView FTree_viewLeft(FTree* tree);

static FTree* FTree_pullLeft(FTree* middle, FDigit* right) {
	if(FTree_empty(middle))
		return FTree_fromDigit(right);
	FView view = FTree_viewLeft(middle);
	FTree* tail = FDeep_make(FTree_size(middle) + right->size,
		FDigit_fromNode(view.node), view.tree,
		FDigit_incRef(right));
	return tail;
}

static FView FTree_viewLeft(FTree* tree) {
	assert(tree != NULL);
	switch(tree->type) {
		case FSingleT: return FView_make(tree->single, FEmpty_make());
		case FDeepT: {
			FDigit* left = tree->deep->left;
			FNode* head = left->items[0];
			if(left->count == 1) return FView_make(head,
				FTree_pullLeft(tree->deep->middle, tree->deep->right));
			for(int i = 1; i < left->count; ++i)
				FNode_incRef(left->items[i]);
			FTree* tail = FDeep_make(tree->deep->size - head->size,
				FDigit_makeN(left->size - head->size,
					left->count - 1, left->items + 1),
				FTree_incRef(tree->deep->middle),
				FDigit_incRef(tree->deep->right));
			return FView_make(head, tail);
		}
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_viewLeft(PSequence* self) {
	if(FTree_empty(self->tree))
		return PyErr_Format(PyExc_IndexError, "view from empty sequence");
	FView view = FTree_viewLeft(self->tree);
	assert(view.node->size == 1);
	return Py_BuildValue("(ON)",
		view.node->value, PSequence_make(view.tree));
}

// }}}

// {{{ viewRight

static FView FTree_viewRight(FTree* tree);

static FTree* FTree_pullRight(FDigit* left, FTree* middle) {
	if(FTree_empty(middle))
		return FTree_fromDigit(left);
	FView view = FTree_viewRight(middle);
	FTree* init = FDeep_make(FTree_size(middle) + left->size,
		FDigit_incRef(left), view.tree,
		FDigit_fromNode(view.node));
	return init;
}

static FView FTree_viewRight(FTree* tree) {
	assert(tree != NULL);
	switch(tree->type) {
		case FSingleT: return FView_make(tree->single, FEmpty_make());
		case FDeepT: {
			FDigit* right = tree->deep->right;
			FNode* last = right->items[right->count-1];
			if(right->count == 1) return FView_make(last,
				FTree_pullRight(tree->deep->left, tree->deep->middle));
			for(int i = 0; i < right->count - 1; ++i)
				FNode_incRef(right->items[i]);
			FTree* init = FDeep_make(tree->deep->size - last->size,
				FDigit_incRef(tree->deep->left),
				FTree_incRef(tree->deep->middle),
				FDigit_makeN(right->size - last->size,
					right->count - 1, right->items));
			return FView_make(last, init);
		}
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_viewRight(PSequence* self) {
	if(FTree_empty(self->tree))
		return PyErr_Format(PyExc_IndexError, "view from empty sequence");
	FView view = FTree_viewRight(self->tree);
	assert(view.node->size == 1);
	return Py_BuildValue("(NO)",
		PSequence_make(view.tree), view.node->value);
}

// }}}

// {{{ peek

static PyObject* FTree_peekLeft(FTree* tree) {
	switch(tree->type) {
		case FEmptyT: return PyErr_Format(
			PyExc_IndexError, "peek from empty sequence");
		case FSingleT:
			assert(tree->single->size == 1);
			return PObj_IncRef(tree->single->value);
		case FDeepT:
			assert(tree->deep->left->items[0]->size == 1);
			return PObj_IncRef(tree->deep->left->items[0]->value);
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_peekLeft(PSequence* self, void*) {
	return FTree_peekLeft(self->tree);
}

static PyObject* FTree_peekRight(FTree* tree) {
	switch(tree->type) {
		case FEmptyT: return PyErr_Format(
			PyExc_IndexError, "peek from empty sequence");
		case FSingleT:
			assert(tree->single->size == 1);
			return PObj_IncRef(tree->single->value);
		case FDeepT: {
			FDigit* right = tree->deep->right;
			assert(right->items[right->count - 1]->size == 1);
			return PObj_IncRef(right->items[right->count - 1]->value);
		}
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_peekRight(PSequence* self, void*) {
	return FTree_peekRight(self->tree);
}

// }}}

// {{{ fromIterable

static FTree* FTree_fromNodes(size_t size, size_t count, FNode** nodes) {
	#ifndef NDEBUG
		size_t sizeD = 0;
		for(size_t i = 0; i < count; ++i)
			sizeD += nodes[i]->size;
		assert(size == sizeD);
	#endif
	if(count == 0) return FEmpty_make();
	if(count == 1) return FSingle_make(nodes[0]);
	if(count <= 8) return FDeep_make(size,
		FDigit_makeNS(count >> 1, nodes), FEmpty_make(),
		FDigit_makeNS(count - (count >> 1), nodes + (count >> 1)));
	FDigit* left = FDigit_makeNS(3, nodes);
	FDigit* right = FDigit_makeNS(3, nodes + (count - 3));
	FNode** input = nodes + 3; FNode** output = nodes;
	FNode *x, *y, *z;
	for(size_t i = (count - 1) / 3; i > 3; --i) {
		x = *input++; y = *input++; z = *input++;
		*output++ = FNode_makeS(x, y, z);
	}
	switch(count % 3) {
		case 0:
			if(count != 9) {
				x = *input++; y = *input++; z = *input++;
				*output++ = FNode_makeS(x, y, z);
			}
			x = *input++; y = *input++; z = *input++;
			*output++ = FNode_makeS(x, y, z);
			break;
		case 1:
			x = *input++; y = *input++;
			*output++ = FNode_makeS(x, y, NULL);
			x = *input++; y = *input++;
			*output++ = FNode_makeS(x, y, NULL);
			break;
		case 2:
			x = *input++; y = *input++; z = *input++;
			*output++ = FNode_makeS(x, y, z);
			x = *input++; y = *input++;
			*output++ = FNode_makeS(x, y, NULL);
			break;
		default: Py_UNREACHABLE();
	}
	size_t sizeN = size - left->size - right->size;
	FTree* tree = FDeep_make(size, left,
		FTree_fromNodes(sizeN, output - nodes, nodes), right);
	return tree;
}

static PSequence* PSequence_fromIterable(PyObject* sequence) {
	assert(sequence != NULL);
	if(Py_TYPE(sequence) == &PSequenceType)
		return PObj_IncRef(sequence);
	if(Py_TYPE(sequence) == &PSequenceEvolverType)
		return PObj_IncRef(((PSequenceEvolver*)sequence)->seq);
	PyObject* seq = PySequence_Fast(sequence, "expected a sequence");
	if(seq == NULL) return NULL;
	Py_ssize_t size = PySequence_Fast_GET_SIZE(seq);
	FNode** nodes = PyMem_Malloc(size * sizeof(FNode*));
	PyObject** iter = PySequence_Fast_ITEMS(seq);
	for(Py_ssize_t i = 0; i < size; ++i)
		nodes[i] = FNode_makeE(PObj_IncRef(*iter++));
	Py_DECREF(seq);
	FTree* tree = FTree_fromNodes(size, size, nodes);
	PyMem_Free(nodes);
	return PSequence_make(tree);
}

// }}}

// {{{ toTuple

static size_t FNode_toTuple(FNode* node, PyObject* tuple, size_t index) {
	assert(node != NULL);
	if(node->size == 1) {
		PyTuple_SET_ITEM(tuple, index, PObj_IncRef(node->value));
		return index + 1;
	}
	index = FNode_toTuple(node->items[0], tuple, index);
	index = FNode_toTuple(node->items[1], tuple, index);
	if(node->items[2] != NULL)
		index = FNode_toTuple(node->items[2], tuple, index);
	return index;
}

static size_t FDigit_toTuple(FDigit* digit, PyObject* tuple, size_t index) {
	assert(digit != NULL);
	for(int i = 0; i < digit->count; ++i)
		index = FNode_toTuple(digit->items[i], tuple, index);
	return index;
}

static size_t FTree_toTuple(FTree* tree, PyObject* tuple, size_t index) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return index;
		case FSingleT: return FNode_toTuple(tree->single, tuple, index);
		case FDeepT:
			index = FDigit_toTuple(tree->deep->left, tuple, index);
			index = FTree_toTuple(tree->deep->middle, tuple, index);
			return FDigit_toTuple(tree->deep->right, tuple, index);
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_toTuple(PSequence* self) {
	size_t size = FTree_size(self->tree);
	PyObject* tuple = PyTuple_New(size);
	if(tuple == NULL) return NULL;
	size_t end UNUSED =
		FTree_toTuple(self->tree, tuple, 0);
	assert(end == size);
	return tuple;
}

// }}}

// {{{ toList

static size_t FNode_toList(FNode* node, PyObject* list, size_t index) {
	assert(node != NULL);
	if(node->size == 1) {
		PyList_SET_ITEM(list, index, PObj_IncRef(node->value));
		return index + 1;
	}
	index = FNode_toList(node->items[0], list, index);
	index = FNode_toList(node->items[1], list, index);
	if(node->items[2] != NULL)
		index = FNode_toList(node->items[2], list, index);
	return index;
}

static size_t FDigit_toList(FDigit* digit, PyObject* list, size_t index) {
	assert(digit != NULL);
	for(int i = 0; i < digit->count; ++i)
		index = FNode_toList(digit->items[i], list, index);
	return index;
}

static size_t FTree_toList(FTree* tree, PyObject* list, size_t index) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return index;
		case FSingleT: return FNode_toList(tree->single, list, index);
		case FDeepT:
			index = FDigit_toList(tree->deep->left, list, index);
			index = FTree_toList(tree->deep->middle, list, index);
			return FDigit_toList(tree->deep->right, list, index);
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_toList(PSequence* self) {
	size_t size = FTree_size(self->tree);
	PyObject* list = PyList_New(size);
	if(list == NULL) return NULL;
	size_t end UNUSED =
		FTree_toList(self->tree, list, 0);
	assert(end == size);
	return list;
}

// }}}

// {{{ getItem

static void* FNode_getItem(const FNode* node, size_t index) {
	assert(node != NULL);
	assert(index < node->size);
	if(node->size == 1)
		return node->value;
	size_t size;
	if(index < (size = node->items[0]->size))
		return FNode_getItem(node->items[0], index);
	index -= size;
	if(index < (size = node->items[1]->size))
		return FNode_getItem(node->items[1], index);
	index -= size;
	return FNode_getItem(node->items[2], index);
}

static void* FDigit_getItem(const FDigit* digit, size_t index) {
	assert(index < digit->size);
	size_t size;
	for(int i = 0; i < digit->count; ++i)
		if(index < (size = digit->items[i]->size))
			return FNode_getItem(digit->items[i], index);
		else
			index -= size;
	Py_UNREACHABLE();
}

static void* FTree_getItem(const FTree* tree, size_t index) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: return FNode_getItem(tree->single, index);
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->left->size))
				return FDigit_getItem(tree->deep->left, index);
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle)))
				return FTree_getItem(tree->deep->middle, index);
			index -= size;
			return FDigit_getItem(tree->deep->right, index);
		} default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_getItem(const PSequence* self, Py_ssize_t index) {
	if(!(0 <= index && index < FTree_ssize(self->tree)))
		return PSequence_indexError(index);
	PyObject* value = FTree_getItem(self->tree, index);
	assert(value != NULL);
	return PObj_IncRef(value);
}

static PyObject* PSequence_getItemS(const PSequence* self, Py_ssize_t index) {
	if(index < 0) index += FTree_ssize(self->tree);
	return PSequence_getItem(self, index);
}

// }}}

// {{{ traverse

static int FNode_traverse(FNode* node, visitproc visit, void* arg) {
	assert(node != NULL);
	if(node->size == 1) {
		Py_VISIT(node->value);
		return 0;
	}
	int ret = FNode_traverse(node->items[0], visit, arg);
	if(ret != 0) return ret;
	ret = FNode_traverse(node->items[1], visit, arg);
	if(ret != 0) return ret;
	if(node->items[2] == NULL) return 0;
	return FNode_traverse(node->items[2], visit, arg);
}

static int FDigit_traverse(FDigit* digit, visitproc visit, void* arg) {
	assert(digit != NULL);
	for(int i = 0; i < digit->count; ++i) {
		int ret = FNode_traverse(digit->items[i], visit, arg);
		if(ret != 0) return ret;
	}
	return 0;
}

static int FTree_traverse(FTree* tree, visitproc visit, void* arg) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return 0;
		case FSingleT: return FNode_traverse(tree->single, visit, arg);
		case FDeepT: {
			int ret = FDigit_traverse(tree->deep->left, visit, arg);
			if(ret != 0) return ret;
			ret = FTree_traverse(tree->deep->middle, visit, arg);
			if(ret != 0) return ret;
			return FDigit_traverse(tree->deep->right, visit, arg);
		}
		default: Py_UNREACHABLE();
	}
}

static int PSequence_traverse(PSequence* self, visitproc visit, void* arg) {
	return FTree_traverse(self->tree, visit, arg);
}

// }}}

// {{{ concat

static FTree* FTree_extend(FTree* xs, FTree* ys);

static FTree* FDeep_extend(FDeep* xs, FDeep* ys) {
	size_t size = xs->size + ys->size;
	FNode* mid[8]; int count = 0;
	for(; count < xs->right->count; ++count)
		mid[count] = FNode_incRef(xs->right->items[count]);
	for(int i = 0; i < ys->left->count; ++i, ++count)
		mid[count] = FNode_incRef(ys->left->items[i]);
	FTree* right = FTree_incRef(ys->middle);
	assert(2 <= count && count <= 8);
	switch(count) {
		case 8: right = FTree_decRefRet(right, FTree_appendLeft(right,
			FNode_makeS(mid[5], mid[6], mid[7])));
		case 5: right = FTree_decRefRet(right, FTree_appendLeft(right,
			FNode_makeS(mid[2], mid[3], mid[4])));
		case 2: right = FTree_decRefRet(right, FTree_appendLeft(right,
			FNode_makeS(mid[0], mid[1], NULL)));
		break;
		case 6: right = FTree_decRefRet(right, FTree_appendLeft(right,
			FNode_makeS(mid[3], mid[4], mid[5])));
		case 3: right = FTree_decRefRet(right, FTree_appendLeft(right,
			FNode_makeS(mid[0], mid[1], mid[2])));
		break;
		case 7: right = FTree_decRefRet(right, FTree_appendLeft(right,
			FNode_makeS(mid[4], mid[5], mid[6])));
		case 4:
			right = FTree_decRefRet(right, FTree_appendLeft(right,
				FNode_makeS(mid[2], mid[3], NULL)));
			right = FTree_decRefRet(right, FTree_appendLeft(right,
				FNode_makeS(mid[0], mid[1], NULL)));
		break;
		default: Py_UNREACHABLE();
	}
	return FTree_decRefRet(right, FDeep_make(size,
		FDigit_incRef(xs->left),
		FTree_extend(xs->middle, right),
		FDigit_incRef(ys->right)));
}

static FTree* FTree_extend(FTree* xs, FTree* ys) {
	switch(xs->type) {
		case FEmptyT: return FTree_incRef(ys);
		case FSingleT: return FTree_appendLeft(ys, FNode_incRef(xs->single));
		case FDeepT: switch(ys->type) {
			case FEmptyT: return FTree_incRef(xs);
			case FSingleT: return FTree_appendRight(xs, FNode_incRef(ys->single));
			case FDeepT: return FDeep_extend(xs->deep, ys->deep);
			default: Py_UNREACHABLE();
		}
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_extendRight(PSequence* self, PyObject* arg) {
	PSequence* other = PSequence_fromIterable(arg);
	if(other == NULL) return NULL;
	PSequence* ret = PSequence_make(FTree_extend(self->tree, other->tree));
	Py_DECREF(other);
	return ret;
}

static PSequence* PSequence_extendLeft(PSequence* self, PyObject* arg) {
	PSequence* other = PSequence_fromIterable(arg);
	if(other == NULL) return NULL;
	PSequence* ret = PSequence_make(FTree_extend(other->tree, self->tree));
	Py_DECREF(other);
	return ret;
}

// }}}

// {{{ repeat

static PSequence* PSequence_repeat(PSequence* self, Py_ssize_t count) {
	if(count <= 0) return PObj_IncRef(EMPTY_SEQUENCE);
	FTree* result = FEmpty_make();
	FTree* tree = FTree_incRef(self->tree);
	if(count & 1) result = FTree_decRefRet(result, FTree_extend(tree, result));
	for(count >>= 1; count != 0; count >>= 1) {
		tree = FTree_decRefRet(tree, FTree_extend(tree, tree));
		if(count & 1) result = FTree_decRefRet(result, FTree_extend(tree, result));
	}
	return PSequence_make(FTree_decRefRet(tree, result));
}

// }}}

// {{{ setItem

static FNode* FNode_setItem(
	const FNode* node,
	size_t index,
	const PyObject* value
) {
	assert(node != NULL);
	assert(index < node->size);
	if(node->size == 1)
		return FNode_makeE(value);
	size_t size;
	if(index < (size = node->items[0]->size))
		return FNode_make(node->size,
			FNode_setItem(node->items[0], index, value),
			FNode_incRef(node->items[1]),
			FNode_incRefM(node->items[2]));
	index -= size;
	if(index < (size = node->items[1]->size))
		return FNode_make(node->size,
			FNode_incRef(node->items[0]),
			FNode_setItem(node->items[1], index, value),
			FNode_incRefM(node->items[2]));
	index -= size;
	return FNode_make(node->size,
		FNode_incRef(node->items[0]),
		FNode_incRef(node->items[1]),
		FNode_setItem(node->items[2], index, value));
}

static FDigit* FDigit_setItem(
	const FDigit* digit,
	size_t index,
	const PyObject* value
) {
	assert(index < digit->size);
	FNode* nodes[4] = { NULL, NULL, NULL, NULL };
	for(int i = 0; i < digit->count; ++i)
		nodes[i] = FNode_incRef(digit->items[i]);
	size_t size;
	for(int i = 0; i < digit->count; ++i)
		if(index < (size =digit->items[i]->size)) {
			FNode_decRef(nodes[i]);
			nodes[i] = FNode_setItem(nodes[i], index, value);
			return FDigit_make(digit->size, digit->count,
				nodes[0], nodes[1], nodes[2], nodes[3]);
		} else index -= size;
	Py_UNREACHABLE();
}

static FTree* FTree_setItem(
	const FTree* tree,
	size_t index,
	const PyObject* value
) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: return FSingle_make(
			FNode_setItem(tree->single, index, value));
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->left->size))
				return FDeep_make(tree->deep->size,
					FDigit_setItem(tree->deep->left, index, value),
					FTree_incRef(tree->deep->middle),
					FDigit_incRef(tree->deep->right));
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle)))
				return FDeep_make(tree->deep->size,
					FDigit_incRef(tree->deep->left),
					FTree_setItem(tree->deep->middle, index, value),
					FDigit_incRef(tree->deep->right));
			index -= size;
			return FDeep_make(tree->deep->size,
				FDigit_incRef(tree->deep->left),
				FTree_incRef(tree->deep->middle),
				FDigit_setItem(tree->deep->right, index, value));
		} default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_setItem(
	PSequence* self,
	Py_ssize_t index,
	PyObject* value
) {
	if(!(0 <= index && index < FTree_ssize(self->tree)))
		return PSequence_indexError(index);
	return PSequence_make(FTree_setItem(
		self->tree, index, PObj_IncRef(value)));
}

static PSequence* PSequence_setItemS(
	PSequence* self,
	Py_ssize_t index,
	PyObject* value
) {
	if(!FTree_checkIndex(self->tree, &index))
		return PSequence_indexError(index);
	return PSequence_make(FTree_setItem(
		self->tree, index, PObj_IncRef(value)));
}

// static PSequence* PSequence_setItemN(
	// PSequence* self,
	// PyObject* args
// ) {
	// Py_ssize_t index; PyObject* value;
	// if(!PyArg_ParseTuple(args, "nO", &index, &value)) return NULL;
	// if(!FTree_checkIndex(self->tree, &index))
		// return PSequence_indexError(index);
	// return PSequence_make(FTree_setItem(
		// self->tree, index, PObj_IncRef(value)));
// }

// }}}

// {{{ msetItem

static FNode* FNode_msetItem(FNode* node, FMset* mset) {
	if(mset->count == 0)
		return FNode_incRef(node);
	if(mset->index + node->size <= mset->items->index1) {
		mset->index += node->size;
		return FNode_incRef(node);
	}
	if(node->size == 1) {
		assert(mset->index == mset->items->index1);
		--mset->count; ++mset->index;
		PyObject* value = (mset->items++)->value;
		return FNode_makeE(PObj_IncRef(value));
	}
	FNode* nodes[3];
	nodes[0] = FNode_msetItem(node->items[0], mset);
	nodes[1] = FNode_msetItem(node->items[1], mset);
	nodes[2] = node->items[2] == NULL ? NULL
		: FNode_msetItem(node->items[2], mset);
	return FNode_make(node->size, nodes[0], nodes[1], nodes[2]);
}

static FDigit* FDigit_msetItem(FDigit* digit, FMset* mset) {
	if(mset->count == 0)
		return FDigit_incRef(digit);
	if(mset->index + digit->size <= mset->items->index1) {
		mset->index += digit->size;
		return FDigit_incRef(digit);
	}
	FNode* nodes[4];
	for(int i = 0; i < digit->count; ++i)
		nodes[i] = FNode_msetItem(digit->items[i], mset);
	return FDigit_makeN(digit->size, digit->count, nodes);
}

static FTree* FTree_msetItem(FTree* tree, FMset* mset) {
	if(mset->count == 0)
		return FTree_incRef(tree);
	if(mset->index + FTree_size(tree) <= mset->items->index1) {
		mset->index += FTree_size(tree);
		return FTree_incRef(tree);
	}
	switch(tree->type) {
		case FSingleT: return FSingle_make(
			FNode_msetItem(tree->single, mset));
		case FDeepT: {
			FDigit* left = FDigit_msetItem(tree->deep->left, mset);
			FTree* middle = FTree_msetItem(tree->deep->middle, mset);
			FDigit* right = FDigit_msetItem(tree->deep->right, mset);
			return FDeep_make(tree->deep->size, left, middle, right);
		}
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_msetItemN(PSequence* self, PyObject* args) {
	Py_ssize_t argc = PyTuple_GET_SIZE(args);
	if(argc == 0) return PObj_IncRef(self);
	FMset mset = { .index = 0, .count = 0, .items = NULL };
	FIndex2* items = (mset.items = PyMem_Malloc(argc * sizeof(FIndex2)));
	items = items;
	for(Py_ssize_t i = 0; i < argc; ++i)
		items[i].value = NULL;
	for(Py_ssize_t index = 0; index < argc; ++index) {
		Py_ssize_t sindex;
		PyObject* arg = PyTuple_GET_ITEM(args, index);
		if(PyIndex_Check(arg)) {
			sindex = PyNumber_AsSsize_t(arg, PyExc_IndexError);
			if(sindex == -1 && PyErr_Occurred()) goto err;
			items[mset.count].value = PyTuple_GetItem(args, ++index);
		} else if(PyTuple_Check(arg)) {
			PyObject* sindexobj = PyTuple_GetItem(arg, 0);
			if(sindexobj == NULL) goto err;
			sindex = PyNumber_AsSsize_t(sindexobj, PyExc_IndexError);
			if(sindex == -1 && PyErr_Occurred()) goto err;
			items[mset.count].value = PyTuple_GetItem(arg, 1);
		} else {
			PyErr_Format(PyExc_TypeError, "expected int or tuple");
			goto err;
		}
		if(items[mset.count].value == NULL) goto err;
		if(!FTree_checkIndex(self->tree, &sindex)) {
			PSequence_indexError(sindex);
			goto err;
		}
		items[mset.count].index1 = (size_t)sindex;
		items[mset.count].index2 = mset.count;
		++mset.count;
	}
	qsort(items, mset.count, sizeof(FIndex2),
		(int(*)(const void*, const void*))FIndex2_compare);
	size_t unique = 0;
	for(size_t i = 0; i < mset.count; ++unique) {
		size_t index = items[i++].index1;
		while(i < mset.count && items[i].index1 == index) ++i;
		items[unique].index1 = items[i-1].index1;
		items[unique].value = items[i-1].value;
	}
	mset.count = unique;
	FTree* tree = FTree_msetItem(self->tree, &mset);
	PyMem_Free(items);
	return PSequence_make(tree);
	err:
		PyMem_Free(items);
		return NULL;
}

// }}}

// {{{ insertItem

static FInsert FNode_insertItem(FNode* node, size_t index, PyObject* item) {
	assert(index < node->size);
	if(node->size == 1) return FInsert_make(
		FNode_incRef(node), FNode_makeE(PObj_IncRef(item)));
	FNode* nodes[4] = { NULL, NULL, NULL, NULL };
	do {
		size_t size;
		if(index < (size = node->items[0]->size)) {
			FInsert ins = FNode_insertItem(node->items[0], index, item);
			nodes[0] = ins.node;
			if(ins.extra == NULL) {
				nodes[1] = FNode_incRef(node->items[1]);
				nodes[2] = FNode_incRefM(node->items[2]);
			} else {
				nodes[1] = ins.extra;
				nodes[2] = FNode_incRef(node->items[1]);
				nodes[3] = FNode_incRefM(node->items[2]);
			}
			break;
		} index -= size;
		nodes[0] = FNode_incRef(node->items[0]);
		if(index < (size = node->items[1]->size)) {
			FInsert ins = FNode_insertItem(node->items[1], index, item);
			nodes[1] = ins.node;
			if(ins.extra == NULL) {
				nodes[2] = FNode_incRefM(node->items[2]);
			} else {
				nodes[2] = ins.extra;
				nodes[3] = FNode_incRefM(node->items[2]);
			}
			break;
		} index -= size;
		nodes[1] = FNode_incRef(node->items[1]);
		assert(node->items[0] != NULL); {
			FInsert ins = FNode_insertItem(node->items[2], index, item);
			nodes[2] = ins.node;
			nodes[3] = ins.extra;
			break;
		}
	} while(0);
	if(nodes[3] == NULL) return FInsert_make(NULL,
		FNode_make(node->size + 1, nodes[0], nodes[1], nodes[2]));
	return FInsert_make(
		FNode_makeS(nodes[2], nodes[3], NULL),
		FNode_makeS(nodes[0], nodes[1], NULL));
}

static FInsert FDigit_insertLeft(FDigit* digit, size_t index, PyObject* item) {
	assert(index < digit->size);
	FNode* nodes[5] = { NULL, NULL, NULL, NULL, NULL };
	int mid = 0, count;
	for(; mid < digit->count; ++mid) {
		if(index < digit->items[mid]->size) break;
		nodes[mid] = FNode_incRef(digit->items[mid]);
		index -= digit->items[mid]->size;
	}
	assert(mid < digit->count);
	FInsert ins = FNode_insertItem(digit->items[mid], index, item);
	nodes[mid] = ins.node;
	if(ins.extra == NULL) {
		assert(ins.node->size == digit->items[mid]->size + 1);
		for(int i = mid + 1; i < digit->count; ++i)
			nodes[i] = FNode_incRef(digit->items[i]);
		count = digit->count;
	} else {
		nodes[mid + 1] = ins.extra;
		assert(ins.node->size + ins.extra->size
			== digit->items[mid]->size + 1);
		for(int i = mid + 1; i < digit->count; ++i)
			nodes[i + 1] = FNode_incRef(digit->items[i]);
		count = digit->count + 1;
	}
	if(nodes[4] == NULL) return FInsert_make(NULL,
		FDigit_makeN(digit->size + 1, count, nodes));
	return FInsert_make(
		FNode_makeS(nodes[2], nodes[3], nodes[4]),
		FDigit_makeNS(2, nodes));
}

static FInsert FDigit_insertRight(FDigit* digit, size_t index, PyObject* item) {
	assert(index < digit->size);
	FNode* nodes[5] = { NULL, NULL, NULL, NULL, NULL };
	int mid = 0, count;
	for(; mid < digit->count; ++mid) {
		if(index < digit->items[mid]->size) break;
		nodes[mid] = FNode_incRef(digit->items[mid]);
		index -= digit->items[mid]->size;
	}
	assert(mid < digit->count);
	FInsert ins = FNode_insertItem(digit->items[mid], index, item);
	nodes[mid] = ins.node;
	if(ins.extra == NULL) {
		assert(ins.node->size == digit->items[mid]->size + 1);
		for(int i = mid + 1; i < digit->count; ++i)
			nodes[i] = FNode_incRef(digit->items[i]);
		count = digit->count;
	} else {
		nodes[mid + 1] = ins.extra;
		assert(ins.node->size + ins.extra->size
			== digit->items[mid]->size + 1);
		for(int i = mid + 1; i < digit->count; ++i)
			nodes[i + 1] = FNode_incRef(digit->items[i]);
		count = digit->count + 1;
	}
	if(nodes[4] == NULL) return FInsert_make(NULL,
		FDigit_makeN(digit->size + 1, count, nodes));
	return FInsert_make(
		FNode_makeS(nodes[0], nodes[1], nodes[2]),
		FDigit_makeNS(2, nodes + 3));
}

static FTree* FTree_insertItem(FTree* tree, size_t index, PyObject* item) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: {
			FInsert ins = FNode_insertItem(tree->single, index, item);
			assert(tree->single->size + 1 ==
				ins.digit->size + (ins.extra == NULL ? 0 : ins.extra->size));
			if(ins.extra == NULL) return FSingle_make(ins.node);
			return FDeep_make(tree->single->size + 1,
				FDigit_make(ins.node->size, 1, ins.node, NULL, NULL, NULL),
				FEmpty_make(),
				FDigit_make(ins.extra->size, 1, ins.extra, NULL, NULL, NULL));
		}
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->left->size)) {
				FInsert ins = FDigit_insertLeft(tree->deep->left, index, item);
				assert(tree->deep->left->size + 1 ==
					ins.digit->size + (ins.extra == NULL ? 0 : ins.extra->size));
				FTree* middle = ins.extra == NULL
					? FTree_incRef(tree->deep->middle)
					: FTree_appendLeft(tree->deep->middle, ins.extra);
				return FDeep_make(tree->deep->size + 1,
					ins.digit, middle, FDigit_incRef(tree->deep->right));
			}
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle))) {
				FTree* middle = FTree_insertItem(tree->deep->middle, index, item);
				assert(FTree_size(tree->deep->middle) + 1 == FTree_size(middle));
				return FDeep_make(tree->deep->size + 1,
					FDigit_incRef(tree->deep->left),
					middle,
					FDigit_incRef(tree->deep->right));
			}
			index -= size;
			assert(index < tree->deep->right->size); {
				FInsert ins = FDigit_insertRight(tree->deep->right, index, item);
				assert(tree->deep->right->size + 1 ==
					ins.digit->size + (ins.extra == NULL ? 0 : ins.extra->size));
				FTree* middle = ins.extra == NULL
					? FTree_incRef(tree->deep->middle)
					: FTree_appendRight(tree->deep->middle, ins.extra);
				return FDeep_make(tree->deep->size + 1,
					FDigit_incRef(tree->deep->left), middle, ins.digit);
			}
		}
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_insertItemN(PSequence* self, PyObject* args) {
	Py_ssize_t index; PyObject* value;
	if(!PyArg_ParseTuple(args, "nO", &index, &value)) return NULL;
	if(!FTree_checkIndex(self->tree, &index)) {
		if(index < 0) return PSequence_appendLeft(self, value);
		return PSequence_appendRight(self, value);
	}
	return PSequence_make(FTree_insertItem(self->tree, index, value));
}

// }}}

// {{{ merge/meld

static FMerge FNode_mergeLeft(FNode* left, FNode* node) {
	if(left == NULL)
		return FMerge_make(FNode_incRef(node), NULL);
	assert(FNode_depth(left) + 1 == FNode_depth(node));
	if(node->items[2] == NULL)
		return FMerge_make(FNode_makeS(
			left,
			FNode_incRef(node->items[0]),
			FNode_incRef(node->items[1])), NULL);
	return FMerge_make(
		FNode_makeS(
			left,
			FNode_incRef(node->items[0]), NULL),
		FNode_makeS(
			FNode_incRef(node->items[1]),
			FNode_incRef(node->items[2]), NULL));
}

static FMerge FNode_mergeRight(FNode* node, FNode* right) {
	if(right == NULL)
		return FMerge_make(FNode_incRef(node), NULL);
	assert(FNode_depth(node) == FNode_depth(right) + 1);
	if(node->items[2] == NULL)
		return FMerge_make(FNode_makeS(
			FNode_incRef(node->items[0]),
			FNode_incRef(node->items[1]),
			right), NULL);
	return FMerge_make(
		FNode_makeS(
			FNode_incRef(node->items[0]),
			FNode_incRef(node->items[1]), NULL),
		FNode_makeS(
			FNode_incRef(node->items[2]),
			right, NULL));
}

static FDigit* FDigit_mergeLeft(FNode* left, FNode* node) {
	if(left == NULL)
		return FDigit_fromNode(node);
	assert(FNode_depth(left) + 2 == FNode_depth(node));
	FMerge merge = FNode_mergeLeft(left, node->items[0]);
	if(merge.extra == NULL)
		return FDigit_makeS(
			FNode_count(node),
			merge.node,
			FNode_incRef(node->items[1]),
			FNode_incRefM(node->items[2]), NULL);
	return FDigit_makeS(
		FNode_count(node) + 1,
		merge.left,
		merge.right,
		FNode_incRef(node->items[1]),
		FNode_incRefM(node->items[2]));
}

static FDigit* FDigit_mergeRight(FNode* node, FNode* right) {
	if(right == NULL)
		return FDigit_fromNode(node);
	assert(FNode_depth(right) + 2 == FNode_depth(node));
	if(node->items[2] == NULL) {
		FMerge merge = FNode_mergeRight(node->items[1], right);
		return FDigit_makeS(merge.extra == NULL ? 2 : 3,
			FNode_incRef(node->items[0]),
			merge.left, merge.right, NULL);
	} else {
		FMerge merge = FNode_mergeRight(node->items[2], right);
		return FDigit_makeS(merge.extra == NULL ? 3 : 4,
			FNode_incRef(node->items[0]),
			FNode_incRef(node->items[1]),
			merge.left, merge.right);
	}
}

static FMeld FNode_meldLeft(FNode* extra, FMerge merge) {
	if(merge.extra != NULL) {
		if(extra == NULL)
			return FMeld_make(true, FNode_makeS(merge.left, merge.right, NULL));
		return FMeld_make(true, FNode_makeS(
			FNode_incRef(extra), merge.left, merge.right));
	}
	if(extra == NULL)
		return FMeld_make(false, merge.node);
	return FMeld_make(true, FNode_makeS(
		FNode_incRef(extra), merge.node, NULL));
}

static FMeld FNode_meldRight(FMerge merge, FNode* extra) {
	if(merge.extra != NULL) 
		return FMeld_make(true, FNode_makeS(
			merge.left, merge.right, FNode_incRefM(extra)));
	if(extra == NULL)
		return FMeld_make(false, merge.node);
	return FMeld_make(true, FNode_makeS(
		merge.node, FNode_incRefM(extra), NULL));
}

// }}}

// {{{ deleteItem

static FMeld FTree_deleteItem(FTree* tree, size_t index);

static FMeld FNode_deleteItem(FNode* node, size_t index) {
	assert(index < node->size);
	if(node->size == 1) return FMeld_make(false, NULL);
	size_t size;
	if(index < (size = node->items[0]->size)) {
		FMeld meld = FNode_deleteItem(node->items[0], index);
		if(meld.full) return FMeld_make(true,
			FNode_make(node->size - 1, meld.node,
				FNode_incRef(node->items[1]),
				FNode_incRefM(node->items[2])));
		return FNode_meldRight(
			FNode_mergeLeft(meld.node, node->items[1]), node->items[2]);
	} index -= size;
	if(index < (size = node->items[1]->size)) {
		FMeld meld = FNode_deleteItem(node->items[1], index);
		if(meld.full) return FMeld_make(true,
			FNode_make(node->size - 1, FNode_incRef(node->items[0]),
				meld.node, FNode_incRefM(node->items[2])));
		return FNode_meldRight(
			FNode_mergeRight(node->items[0], meld.node), node->items[2]);
	} index -= size;
	assert(node->items[2] != NULL); {
		FMeld meld = FNode_deleteItem(node->items[2], index);
		if(meld.full) return FMeld_make(true,
			FNode_make(node->size - 1, FNode_incRef(node->items[0]),
				FNode_incRef(node->items[1]), meld.node));
		return FNode_meldLeft(node->items[0],
			FNode_mergeRight(node->items[1], meld.node));
	}
}

static FMeld FDigit_deleteItem(FDigit* digit, size_t index) {
	assert(index < digit->size);
	FNode* nodes[4] = { NULL, NULL, NULL, NULL };
	int mid = 0, count;
	for(; mid < digit->count; ++mid) {
		if(index < digit->items[mid]->size) break;
		nodes[mid] = FNode_incRef(digit->items[mid]);
		index -= digit->items[mid]->size;
	}
	assert(mid < digit->count);
	FMeld meld = FNode_deleteItem(digit->items[mid], index);
	if(meld.full) {
		nodes[mid] = meld.node;
		for(int i = mid + 1; i < digit->count; ++i)
			nodes[i] = FNode_incRef(digit->items[i]);
		count = digit->count;
	} else if(digit->count == 1) {
		return meld;
	} else if(mid + 1 == digit->count) {
		FNode_decRef(nodes[mid - 1]);
		FMerge merge = FNode_mergeRight(digit->items[mid - 1], meld.node);
		nodes[mid - 1] = merge.left;
		if(merge.extra == NULL) {
			for(int i = mid + 1; i < digit->count; ++i)
				nodes[i - 1] = FNode_incRef(digit->items[i]);
			count = digit->count - 1;
		} else {
			nodes[mid] = merge.right;
			for(int i = mid + 1; i < digit->count; ++i)
				nodes[i] = FNode_incRef(digit->items[i]);
			count = digit->count;
		}
	} else {
		FMerge merge = FNode_mergeLeft(meld.node, digit->items[mid + 1]);
		nodes[mid] = merge.left;
		if(merge.extra == NULL) {
			for(int i = mid + 2; i < digit->count; ++i)
				nodes[i - 1] = FNode_incRef(digit->items[i]);
			count = digit->count - 1;
		} else {
			nodes[mid + 1] = merge.right;
			for(int i = mid + 2; i < digit->count; ++i)
				nodes[i] = FNode_incRef(digit->items[i]);
			count = digit->count;
		}
	}
	return FMeld_make(true, FDigit_makeNS(count, nodes));
}

static FMeld FTree_deleteItemLeft(FTree* tree, size_t index) {
	FMeld meld = FDigit_deleteItem(tree->deep->left, index);
	if(meld.full) return FMeld_make(true, FDeep_make(tree->deep->size - 1,
		meld.digit,
		FTree_incRef(tree->deep->middle),
		FDigit_incRef(tree->deep->right)));
	if(!FTree_empty(tree->deep->middle)) {
		FView view = FTree_viewLeft(tree->deep->middle);
		return FMeld_make(true, FDeep_make(tree->deep->size - 1,
			FDigit_mergeLeft(meld.node, view.node),
			view.tree,
			FDigit_incRef(tree->deep->right)));
	}
	FMerge merge = FNode_mergeLeft(meld.node, tree->deep->right->items[0]);
	if(tree->deep->right->count == 1)
		return FMeld_make(true, FTree_fromMerge(merge));
	for(int i = 1; i < tree->deep->right->count; ++i)
		FNode_incRef(tree->deep->right->items[i]);
	return FMeld_make(true, FDeep_make(tree->deep->size - 1,
		FDigit_fromMerge(merge),
		FEmpty_make(),
		FDigit_makeNS(tree->deep->right->count - 1,
			tree->deep->right->items + 1)));
}

static FMeld FTree_deleteItemRight(FTree* tree, size_t index) {
	FMeld meld = FDigit_deleteItem(tree->deep->right, index);
	if(meld.full) return FMeld_make(true, FDeep_make(tree->deep->size - 1,
		FDigit_incRef(tree->deep->left),
		FTree_incRef(tree->deep->middle),
		meld.digit));
	if(!FTree_empty(tree->deep->middle)) {
		FView view = FTree_viewRight(tree->deep->middle);
		return FMeld_make(true, FDeep_make(tree->deep->size - 1,
			FDigit_incRef(tree->deep->left),
			view.tree,
			FDigit_mergeRight(view.node, meld.node)));
	}
	FMerge merge = FNode_mergeRight(
		tree->deep->left->items[tree->deep->left->count - 1], meld.node);
	if(tree->deep->left->count == 1)
		return FMeld_make(true, FTree_fromMerge(merge));
	for(int i = 0; i < tree->deep->left->count - 1; ++i)
		FNode_incRef(tree->deep->left->items[i]);
	return FMeld_make(true, FDeep_make(tree->deep->size - 1,
		FDigit_makeNS(tree->deep->left->count - 1,
			tree->deep->left->items),
		FEmpty_make(),
		FDigit_fromMerge(merge)));
}

static FMeld FTree_deleteItemMiddle(FTree* tree, size_t index) {
	FMeld meld = FTree_deleteItem(tree->deep->middle, index);
	if(meld.full) return FMeld_make(true, FDeep_make(tree->deep->size - 1,
		FDigit_incRef(tree->deep->left),
		meld.tree,
		FDigit_incRef(tree->deep->right)));
	FNode* nodes[4];
	for(int i = 0; i < tree->deep->left->count; ++i)
		nodes[i] = FNode_incRef(tree->deep->left->items[i]);
	if(tree->deep->left->count < 4) {
		nodes[tree->deep->left->count] = meld.node;
		return FMeld_make(true, FDeep_make(tree->deep->size - 1,
			FDigit_makeN(
				tree->deep->left->size + FTree_size(tree->deep->middle) - 1,
				tree->deep->left->count + 1, nodes),
			FEmpty_make(),
			FDigit_incRef(tree->deep->right)));
	}
	return FMeld_make(true, FDeep_make(tree->deep->size - 1,
		FDigit_makeNS(2, nodes),
		FSingle_make(FNode_makeS(nodes[2], nodes[3], meld.node)),
		FDigit_incRef(tree->deep->right)));
}

static FMeld FTree_deleteItem(FTree* tree, size_t index) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: {
			FMeld meld = FNode_deleteItem(tree->single, index);
			if(meld.full) meld.tree = FSingle_make(meld.node);
			return meld;
		}
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->left->size))
				return FTree_deleteItemLeft(tree, index);
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle)))
				return FTree_deleteItemMiddle(tree, index);
			index -= size;
			assert(index < tree->deep->right->size);
			return FTree_deleteItemRight(tree, index);
		}
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_deleteItem(PSequence* self, Py_ssize_t index) {
	if(!(0 <= index && index < FTree_ssize(self->tree)))
		return PSequence_indexError(index);
	FMeld meld = FTree_deleteItem(self->tree, index);
	assert((meld.node == NULL) == !meld.full);
	if(!meld.full) return PObj_IncRef(EMPTY_SEQUENCE);
	return PSequence_make(meld.tree);
}

static PSequence* PSequence_deleteItemS(PSequence* self, Py_ssize_t index) {
	if(!FTree_checkIndex(self->tree, &index))
		return PSequence_indexError(index);
	FMeld meld = FTree_deleteItem(self->tree, index);
	assert((meld.node == NULL) == !meld.full);
	if(!meld.full) return PObj_IncRef(EMPTY_SEQUENCE);
	return PSequence_make(meld.tree);
}

// }}}

// {{{ contains

static int FNode_contains(FNode* node, PyObject* arg) {
	assert(node != NULL);
	if(node->size == 1)
		return PyObject_RichCompareBool(node->value, arg, Py_EQ);
	int comp;
	if((comp = FNode_contains(node->items[0], arg)) != 0) return comp;
	if((comp = FNode_contains(node->items[1], arg)) != 0) return comp;
	if(node->items[2] == NULL) return 0;
	return FNode_contains(node->items[2], arg);
}

static int FDigit_contains(FDigit* digit, PyObject* arg) {
	assert(digit != NULL);
	for(int i = 0; i < digit->count; ++i) {
		int comp = FNode_contains(digit->items[i], arg);
		if(comp != 0) return comp;
	}
	return 0;
}

static int FTree_contains(FTree* tree, PyObject* arg) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return 0;
		case FSingleT: return FNode_contains(tree->single, arg);
		case FDeepT: {
			int comp;
			if((comp = FDigit_contains(tree->deep->left, arg)) != 0) return comp;
			if((comp = FDigit_contains(tree->deep->right, arg)) != 0) return comp;
			return FTree_contains(tree->deep->middle, arg);
		} default: Py_UNREACHABLE();
	}
}

static int PSequence_contains(PSequence* self, PyObject* arg) {
	return FTree_contains(self->tree, arg);
}

// }}}

// {{{ indexItem

#define check_and_return(index, offset) do { \
	Py_ssize_t _idx = index; \
	if(_idx < 0) return _idx; \
	if(_idx > 0) return _idx + (offset); \
	} while(0)

static Py_ssize_t FNode_indexItem(FNode* node, PyObject* arg) {
	assert(node != NULL);
	if(node->size == 1) return (Py_ssize_t)
		PyObject_RichCompareBool(node->value, arg, Py_EQ);
	check_and_return(FNode_indexItem(node->items[0], arg), 0);
	check_and_return(FNode_indexItem(node->items[1], arg),
		node->items[0]->size);
	if(node->items[2] == NULL) return 0;
	check_and_return(FNode_indexItem(node->items[2], arg),
		node->items[0]->size + node->items[1]->size);
	return 0;
}

static Py_ssize_t FDigit_indexItem(FDigit* digit, PyObject* arg) {
	assert(digit != NULL);
	int offset = 0;
	for(int i = 0; i < digit->count; ++i) {
		check_and_return(FNode_indexItem(digit->items[i], arg), offset);
		offset += digit->items[i]->size;
	}
	return 0;
}

static Py_ssize_t FTree_indexItem(FTree* tree, PyObject* arg) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return 0;
		case FSingleT: return FNode_indexItem(tree->single, arg);
		case FDeepT: {
			check_and_return(FDigit_indexItem(tree->deep->left, arg), 0);
			check_and_return(FTree_indexItem(tree->deep->middle, arg),
				tree->deep->left->size);
			check_and_return(FDigit_indexItem(tree->deep->right, arg),
				tree->deep->left->size + FTree_size(tree->deep->middle));
			return 0;
		} default: Py_UNREACHABLE();
	}
}

#undef check_and_return

static PyObject* PSequence_indexItem(PSequence* self, PyObject* arg) {
	Py_ssize_t index = FTree_indexItem(self->tree, arg);
	if(index < 0) return NULL;
	if(index == 0)
		return PyErr_Format(PyExc_ValueError, "value not in sequence");
	return PyLong_FromSsize_t(index - 1);
}

// }}}

// {{{ removeItem

static PSequence* PSequence_removeItemN(PSequence* self, PyObject* arg) {
	Py_ssize_t index = FTree_indexItem(self->tree, arg);
	if(index < 0) return NULL;
	if(index == 0) return (void*)
		PyErr_Format(PyExc_ValueError, "value not in sequence");
	assert(0 < index && index <= FTree_ssize(self->tree));
	FMeld meld = FTree_deleteItem(self->tree, (size_t)index - 1);
	assert((meld.node == NULL) == !meld.full);
	if(!meld.full) return PObj_IncRef(EMPTY_SEQUENCE);
	return PSequence_make(meld.tree);
}

// }}}

// {{{ countItem

static Py_ssize_t FNode_countItem(FNode* node, PyObject* arg) {
	assert(node != NULL);
	if(node->size == 1)
		return (Py_ssize_t)PyObject_RichCompareBool(node->value, arg, Py_EQ);
	int comp, total;
	if((comp = FNode_countItem(node->items[0], arg)) < 0) return comp;
	total = comp;
	if((comp = FNode_countItem(node->items[1], arg)) < 0) return comp;
	total += comp;
	if(node->items[2] == NULL) return total;
	if((comp = FNode_countItem(node->items[2], arg)) < 0) return comp;
	return total + comp;
}

static Py_ssize_t FDigit_countItem(FDigit* digit, PyObject* arg) {
	assert(digit != NULL);
	int total = 0;
	for(int i = 0; i < digit->count; ++i) {
		int comp = FNode_countItem(digit->items[i], arg);
		if(comp < 0) return comp;
		total += comp;
	}
	return total;
}

static Py_ssize_t FTree_countItem(FTree* tree, PyObject* arg) {
	assert(tree != NULL);
	switch(tree->type) {
		case FEmptyT: return 0;
		case FSingleT: return FNode_countItem(tree->single, arg);
		case FDeepT: {
			int comp, total;
			if((comp = FDigit_countItem(tree->deep->left, arg)) < 0) return comp;
			total = comp;
			if((comp = FTree_countItem(tree->deep->middle, arg)) < 0) return comp;
			total += comp;
			if((comp = FDigit_countItem(tree->deep->right, arg)) < 0) return comp;
			return total + comp;
		} default: Py_UNREACHABLE();
	}
}

static PyObject* PSequence_countItem(PSequence* self, PyObject* arg) {
	return PyLong_FromSsize_t(FTree_countItem(self->tree, arg));
}

// }}}

// {{{ splitView

static FSplit FTree_splitView(FTree* tree, size_t index);

static FSplit FDeep_splitViewLeft(FDeep* deep, size_t index) {
	size_t size, dsize = 0;
	for(int i = 0; i < deep->left->count; ++i)
		FNode_incRef(deep->left->items[i]);
	for(int i = 0; i < deep->left->count; ++i)
		if(index >= (size = deep->left->items[i]->size)) {
			index -= size; dsize += size;
		} else return FSplit_make(
			FTree_fromNodes(dsize, i, deep->left->items),
			FNode_decRefRet(deep->left->items[i], deep->left->items[i]),
			i + 1 == deep->left->count
				? FTree_pullLeft(deep->middle, deep->right)
				: FDeep_make(deep->size - dsize - size,
					FDigit_makeN(deep->left->size - dsize - size,
						deep->left->count - i - 1, deep->left->items + i + 1),
					FTree_incRef(deep->middle), FDigit_incRef(deep->right)));
	Py_UNREACHABLE();
}

static FSplit FDeep_splitViewRight(FDeep* deep, size_t index) {
	size_t size, dsize = 0;
	for(int i = 0; i < deep->right->count; ++i)
		FNode_incRef(deep->right->items[i]);
	for(int i = 0; i < deep->right->count; ++i)
		if(index >= (size = deep->right->items[i]->size)) {
			index -= size; dsize += size;
		} else return FSplit_make(
			i == 0 ? FTree_pullRight(deep->left, deep->middle)
				: FDeep_make(deep->size - deep->right->size + dsize,
					FDigit_incRef(deep->left), FTree_incRef(deep->middle),
					FDigit_makeN(dsize, i, deep->right->items)),
			FNode_decRefRet(deep->right->items[i], deep->right->items[i]),
			FTree_fromNodes(deep->right->size - dsize - size,
				deep->right->count - i - 1, deep->right->items + i + 1));
	Py_UNREACHABLE();
}

static FSplit FDeep_splitViewMiddle(FDeep* deep, size_t index) {
	FSplit split = FTree_splitView(deep->middle, index);
	assert(split.node->size != 1);
	index -= FTree_size(split.left);
	size_t size, prefix = 0;
	if(index < (size = split.node->items[0]->size)) {
		FTree* left = FTree_decRefRet(split.left,
			FTree_pullRight(deep->left, split.left));
		FNode* middle = split.node->items[0];
		FTree* right = FDeep_makeS(
			FDigit_make(split.node->size - size,
				FNode_count(split.node) - 1,
				FNode_incRef(split.node->items[1]),
				FNode_incRefM(split.node->items[2]), NULL, NULL),
			split.right, FDigit_incRef(deep->right));
		return FSplit_make(left, middle, right);
	}
	index -= size; prefix += size;
	if(index < (size = split.node->items[1]->size)) {
		FTree* left = FDeep_makeS(
			FDigit_incRef(deep->left), split.left,
			FDigit_make(split.node->items[0]->size, 1,
				FNode_incRef(split.node->items[0]), NULL, NULL, NULL));
		FNode* middle = split.node->items[1];
		FTree* right = split.node->items[2] == NULL
			? FTree_decRefRet(split.right,
				FTree_pullLeft(split.right, deep->right))
			: FDeep_makeS(FDigit_make(split.node->items[2]->size, 1,
					FNode_incRef(split.node->items[2]), NULL, NULL, NULL),
				split.right, FDigit_incRef(deep->right));
		return FSplit_make(left, middle, right);
	}
	index -= size; prefix += size;
	assert(split.node->items[2] != NULL); {
		size = split.node->items[2]->size;
		FTree* left = FDeep_makeS(
			FDigit_incRef(deep->left), split.left,
			FDigit_make(split.node->size - size, 2,
				FNode_incRef(split.node->items[0]),
				FNode_incRef(split.node->items[1]), NULL, NULL));
		FNode* middle = split.node->items[2];
		FTree* right = FTree_decRefRet(split.right,
			FTree_pullLeft(split.right, deep->right));
		return FSplit_make(left, middle, right);
	}
}

static FSplit FTree_splitView(FTree* tree, size_t index) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: return FSplit_make(FEmpty_make(),
			tree->single, FEmpty_make());
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->left->size))
				return FDeep_splitViewLeft(tree->deep, index);
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle)))
				return FDeep_splitViewMiddle(tree->deep, index);
			index -= size;
			return FDeep_splitViewRight(tree->deep, index);
		} default: Py_UNREACHABLE();
	}
}

// splitAt has to split nodes anyway, so just reuse splitView
static PyObject* PSequence_splitAt(PSequence* self, PyObject* arg) {
	Py_ssize_t index = PyNumber_AsSsize_t(arg, PyExc_IndexError);
	if(index == -1 && PyErr_Occurred()) return NULL;
	if(!FTree_checkIndex(self->tree, &index) || index == 0) {
		if(index <= 0) return Py_BuildValue("(OO)", EMPTY_SEQUENCE, self);
		else return Py_BuildValue("(OO)", self, EMPTY_SEQUENCE);
	}
	FSplit split = FTree_splitView(self->tree, index);
	return Py_BuildValue("(NN)", PSequence_make(split.left),
		PSequence_make(FTree_decRefRet(split.right,
			FTree_appendLeft(split.right, FNode_incRef(split.node)))));
}

static PyObject* PSequence_view(PSequence* self, PyObject* args) {
	Py_ssize_t argc = PyTuple_GET_SIZE(args);
	if(argc == 1) {
		Py_ssize_t index = PyNumber_AsSsize_t(
			PyTuple_GET_ITEM(args, 0), PyExc_IndexError);
		if(index == -1 && PyErr_Occurred()) return NULL;
		if(!FTree_checkIndex(self->tree, &index))
			return PSequence_indexError(index);
		FSplit split = FTree_splitView(self->tree, index);
		return Py_BuildValue("(NON)", PSequence_make(split.left),
			split.node->value, PSequence_make(split.right));
	}
	PyObject* items = PyTuple_New(2 * argc + 1);
	FTree* rest = FTree_incRef(self->tree);
	Py_ssize_t last = 0;
	Py_ssize_t argn = 0;
	for(; argn < argc; ++argn) {
		Py_ssize_t index = PyNumber_AsSsize_t(
			PyTuple_GET_ITEM(args, argn), PyExc_IndexError);
		if(index == -1 && PyErr_Occurred()) goto err;
		if(!FTree_checkIndex(self->tree, &index))
			return PSequence_indexError(index);
		if(index < last) {
			PyErr_Format(PyExc_IndexError,
				"indices ust be in sorted order");
			goto err;
		}
		FSplit split = FTree_splitView(rest, index - last);
		PyTuple_SET_ITEM(items, 2 * argn, (PyObject*)PSequence_make(split.left));
		PyTuple_SET_ITEM(items, 2 * argn + 1, PObj_IncRef(split.node->value));
		rest = FTree_decRefRet(rest, split.right);
		last = index + 1;
	}
	PyTuple_SET_ITEM(items, 2 * argc, (PyObject*)PSequence_make(rest));
	return items;
	err:
		// fill rest of tuple with Nones before deleting
		for(; argn < argc; ++argn) {
			PyTuple_SET_ITEM(items, 2 * argn, PObj_IncRef(Py_None));
			PyTuple_SET_ITEM(items, 2 * argn + 1, PObj_IncRef(Py_None));
		}
		PyTuple_SET_ITEM(items, 2 * argc, PObj_IncRef(Py_None));
		Py_DECREF(items);
		FTree_decRef(rest);
		return NULL;
}

// }}}

// {{{ chunksOf

static PSequence* PSequence_chunksOf(PSequence* self, Py_ssize_t chunk) {
	if(FTree_empty(self->tree)) return PObj_IncRef(self);
	if(chunk <= 0) return (void*)PyErr_Format(
		PyExc_ValueError, "chunk size must be positive");
	FTree* left = FEmpty_make();
	FTree* right = FTree_incRef(self->tree);
	for(Py_ssize_t size = FTree_ssize(self->tree); size > chunk; size -= chunk) {
		FSplit split = FTree_splitView(right, chunk);
		left = FTree_decRefRet(left, FTree_appendRight(left,
			FNode_makeE((PyObject*)PSequence_make(split.left))));
		right = FTree_decRefRet(right, FTree_decRefRet(split.right,
			FTree_appendLeft(split.right, FNode_incRef(split.node))));
	}
	return FTree_decRefRet(left, PSequence_make(FTree_appendRight(left,
		FNode_makeE((PyObject*)PSequence_make(right)))));
}

static PSequence* PSequence_chunksOfN(PSequence* self, PyObject* arg) {
	Py_ssize_t chunk = PyNumber_AsSsize_t(arg, PyExc_IndexError);
	if(chunk == -1 && PyErr_Occurred()) return NULL;
	return PSequence_chunksOf(self, chunk);
}

// }}}

// {{{ takeLeft

static FView FTree_takeLeft(FTree* tree, size_t index);

static FView FDeep_takeLeftLeft(FDeep* deep, size_t index) {
	size_t size, dsize = 0;
	for(int i = 0; i < deep->left->count; ++i)
		if(index >= (size = deep->left->items[i]->size)) {
			FNode_incRef(deep->left->items[i]);
			index -= size; dsize += size;
		} else return FView_make(deep->left->items[i],
			FTree_fromNodes(dsize, i, deep->left->items));
	Py_UNREACHABLE();
}

static FView FDeep_takeLeftRight(FDeep* deep, size_t index) {
	size_t size, dsize = 0;
	for(int i = 0; i < deep->right->count; ++i)
		if(index >= (size = deep->right->items[i]->size)) {
			FNode_incRef(deep->right->items[i]);
			index -= size; dsize += size;
		} else return FView_make(
			deep->right->items[i],
			i == 0 ? FTree_pullRight(deep->left, deep->middle)
				: FDeep_make(deep->size - deep->right->size + dsize,
					FDigit_incRef(deep->left), FTree_incRef(deep->middle),
					FDigit_makeN(dsize, i, deep->right->items)));
	Py_UNREACHABLE();
}

static FView FDeep_takeLeftMiddle(FDeep* deep, size_t index) {
	assert(index < deep->size);
	FView view = FTree_takeLeft(deep->middle, index);
	assert(view.node->size != 1);
	assert(index >= FTree_size(view.tree));
	index -= FTree_size(view.tree);
	size_t size;
	if(index < (size = view.node->items[0]->size))
		return FView_make(view.node->items[0],
			FTree_decRefRet(view.tree,
				FTree_pullRight(deep->left, view.tree)));
	index -= size;
	if(index < (size = view.node->items[1]->size))
		return FView_make(view.node->items[1], FDeep_makeS(
			FDigit_incRef(deep->left), view.tree,
			FDigit_make(view.node->items[0]->size, 1,
				FNode_incRef(view.node->items[0]), NULL, NULL, NULL)));
	assert(view.node->items[2] != NULL);
	index -= size;
	return FView_make(view.node->items[2], FDeep_makeS(
		FDigit_incRef(deep->left), view.tree,
		FDigit_make(view.node->items[0]->size + view.node->items[1]->size, 2,
			FNode_incRef(view.node->items[0]),
			FNode_incRef(view.node->items[1]), NULL, NULL)));
}

static FView FTree_takeLeft(FTree* tree, size_t index) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: return FView_make(tree->single, FEmpty_make());
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->left->size))
				return FDeep_takeLeftLeft(tree->deep, index);
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle)))
				return FDeep_takeLeftMiddle(tree->deep, index);
			index -= size;
			return FDeep_takeLeftRight(tree->deep, index);
		} default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_takeLeft(PSequence* self, Py_ssize_t index) {
	if(index <= 0) return PObj_IncRef(EMPTY_SEQUENCE);
	if((size_t)index >= FTree_size(self->tree)) return PObj_IncRef(self);
	FView view = FTree_takeLeft(self->tree, index);
	return PSequence_make(view.tree);
}

// }}}

// {{{ takeRight

static FView FTree_takeRight(FTree* tree, size_t index);

static FView FDeep_takeRightLeft(FDeep* deep, size_t index) {
	size_t size, dsize = 0;
	for(int i = deep->left->count; i-- > 0;)
		if(index >= (size = deep->left->items[i]->size)) {
			FNode_incRef(deep->left->items[i]);
			index -= size; dsize += size;
		} else return FView_make(
			deep->left->items[i],
			i == deep->left->count - 1
				? FTree_pullLeft(deep->middle, deep->right)
				: FDeep_make(deep->size - deep->left->size + dsize,
					FDigit_makeN(dsize, deep->left->count - i - 1,
						deep->left->items + i + 1),
					FTree_incRef(deep->middle), FDigit_incRef(deep->right)));
	Py_UNREACHABLE();
}

static FView FDeep_takeRightRight(FDeep* deep, size_t index) {
	size_t size, dsize = 0;
	for(int i = deep->right->count; i-- > 0;)
		if(index >= (size = deep->right->items[i]->size)) {
			FNode_incRef(deep->right->items[i]);
			index -= size; dsize += size;
		} else return FView_make(deep->right->items[i],
			FTree_fromNodes(dsize, deep->right->count - i - 1,
				deep->right->items + i + 1));
	Py_UNREACHABLE();
}

static FView FDeep_takeRightMiddle(FDeep* deep, size_t index) {
	assert(index < deep->size);
	FView view = FTree_takeRight(deep->middle, index);
	assert(view.node->size != 1);
	assert(index >= FTree_size(view.tree));
	index -= FTree_size(view.tree);
	size_t size;
	if(view.node->items[2] != NULL) {
		if(index < (size = view.node->items[2]->size))
			return FView_make(view.node->items[2],
				FTree_decRefRet(view.tree,
					FTree_pullLeft(view.tree, deep->right)));
		index -= size;
	}
	if(index < (size = view.node->items[1]->size))
		return FView_make(view.node->items[1],
			view.node->items[2] == NULL
				? FTree_decRefRet(view.tree,
					FTree_pullLeft(view.tree, deep->right))
				: FDeep_makeS(
					FDigit_make(view.node->items[2]->size, 1,
						FNode_incRef(view.node->items[2]), NULL, NULL, NULL),
					view.tree, FDigit_incRef(deep->right)));
	index -= size;
	return FView_make(view.node->items[0], FDeep_makeS(
		FDigit_make(view.node->size - view.node->items[0]->size,
			FNode_count(view.node) - 1,
			FNode_incRef(view.node->items[1]),
			FNode_incRefM(view.node->items[2]), NULL, NULL),
		view.tree, FDigit_incRef(deep->right)));
}

static FView FTree_takeRight(FTree* tree, size_t index) {
	assert(index < FTree_size(tree));
	switch(tree->type) {
		case FSingleT: return FView_make(tree->single, FEmpty_make());
		case FDeepT: {
			size_t size;
			if(index < (size = tree->deep->right->size))
				return FDeep_takeRightRight(tree->deep, index);
			index -= size;
			if(index < (size = FTree_size(tree->deep->middle)))
				return FDeep_takeRightMiddle(tree->deep, index);
			index -= size;
			return FDeep_takeRightLeft(tree->deep, index);
		} default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_takeRight(PSequence* self, Py_ssize_t index) {
	if(index <= 0) return PObj_IncRef(EMPTY_SEQUENCE);
	if((size_t)index >= FTree_size(self->tree)) return PObj_IncRef(self);
	FView view = FTree_takeRight(self->tree, index);
	return PSequence_make(view.tree);
}

// }}}

// {{{ repr

static PyObject* PSequence_repr(PSequence* self) {
	PyObject* list = PSequence_toList(self);
	if(list == NULL) return NULL;
	PyObject* repr = PyObject_Repr(list);
	Py_DECREF(list);
	if(repr == NULL) return NULL;
	PyObject* form = PyUnicode_FromFormat("%s%U%s", "psequence(", repr, ")");
	Py_DECREF(repr);
	return form;
}

// }}}

// {{{ compare

static PyObject* PObj_compare(PyObject* x, PyObject* y, int op) {
	if(x == NULL) {
		if(y == NULL) switch(op) {
			case Py_EQ: case Py_GE: case Py_LE:
				return PObj_IncRef(Py_True);
			case Py_NE: case Py_GT: case Py_LT:
				return PObj_IncRef(Py_False);
			default: Py_UNREACHABLE();
		} else switch(op) {
			case Py_NE: case Py_LT: case Py_LE:
				return PObj_IncRef(Py_True);
			case Py_EQ: case Py_GT: case Py_GE:
				return PObj_IncRef(Py_False);
			default: Py_UNREACHABLE();
		}
	}
	if(y == NULL) switch(op) {
		case Py_NE: case Py_GT: case Py_GE:
			return PObj_IncRef(Py_True);
		case Py_EQ: case Py_LT: case Py_LE:
			return PObj_IncRef(Py_False);
		default: Py_UNREACHABLE();
	}
	int eq = PyObject_RichCompareBool(x, y, Py_EQ);
	if(eq != 0) return NULL;
	switch(op) {
		case Py_EQ: return PObj_IncRef(Py_False);
		case Py_NE: return PObj_IncRef(Py_True);
	}
	int gt = PyObject_RichCompareBool(x, y, Py_GT);
	if(gt == -1) return NULL;
	switch(op) {
		case Py_GT: case Py_GE:
			return PObj_IncRef(gt == 0 ? Py_False : Py_True);
		case Py_LT: case Py_LE:
			return PObj_IncRef(gt == 0 ? Py_True : Py_False);
	}
	Py_UNREACHABLE();
}

static PyObject* PIter_compare(PyObject* xs, PyObject* ys, int op) {
	PyObject* x = PyIter_Next(xs);
	if(x == NULL && PyErr_Occurred()) return NULL;
	PyObject* y = PyIter_Next(ys);
	if(y == NULL && PyErr_Occurred()) {
		if(x != NULL) Py_DECREF(x);
		return NULL;
	}
	PyObject* cmp = PObj_compare(x, y, op);
	if(x != NULL) Py_DECREF(x);
	if(y != NULL) Py_DECREF(y);
	if(cmp != NULL || PyErr_Occurred()) return cmp;
	return PIter_compare(xs, ys, op);
}

static PyObject* PSequence_compare(PyObject* xs, PyObject* ys, int op) {
	if(xs == ys) switch(op) {
		case Py_EQ: case Py_LE: case Py_GE:
			return PObj_IncRef(Py_True);
		case Py_NE: case Py_LT: case Py_GT:
			return PObj_IncRef(Py_False);
		default: Py_UNREACHABLE();
	}
	PyObject* xi = PyObject_GetIter(xs);
	if(xi == NULL) return NULL;
	PyObject* yi = PyObject_GetIter(ys);
	if(yi == NULL) {
		Py_DECREF(xi);
		return NULL;
	}
	PyObject* cmp = PIter_compare(xi, yi, op);
	Py_DECREF(xi);
	Py_DECREF(yi);
	return cmp;
}

// }}}

// {{{ hash

// taken from
// https://github.com/python/cpython/blob/2ef73be8/Objects/tupleobject.c#L320-L344

#if SIZEOF_PY_UHASH_T > 4
#define _PyHASH_XXPRIME_1 ((Py_uhash_t)11400714785074694791ULL)
#define _PyHASH_XXPRIME_2 ((Py_uhash_t)14029467366897019727ULL)
#define _PyHASH_XXPRIME_5 ((Py_uhash_t)2870177450012600261ULL)
#define _PyHASH_XXROTATE(x) ((x << 31) | (x >> 33))
#else
#define _PyHASH_XXPRIME_1 ((Py_uhash_t)2654435761UL)
#define _PyHASH_XXPRIME_2 ((Py_uhash_t)2246822519UL)
#define _PyHASH_XXPRIME_5 ((Py_uhash_t)374761393UL)
#define _PyHASH_XXROTATE(x) ((x << 13) | (x >> 19))
#endif

static Py_uhash_t FNode_hash(FNode* node, Py_uhash_t acc) {
	if(node->size == 1) {
		Py_uhash_t lane = PyObject_Hash(node->value);
		if (lane == (Py_uhash_t)-1) return -1;
		acc += lane * _PyHASH_XXPRIME_2;
		acc = _PyHASH_XXROTATE(acc);
		acc *= _PyHASH_XXPRIME_1;
		return acc;
	}
	if((acc = FNode_hash(node->items[0], acc)) == (Py_uhash_t)-1) return -1;
	if((acc = FNode_hash(node->items[1], acc)) == (Py_uhash_t)-1) return -1;
	if(node->items[2] == NULL) return acc;
	return FNode_hash(node->items[2], acc);
}

static Py_uhash_t FDigit_hash(FDigit* digit, Py_uhash_t acc) {
	for(int i = 0; i < digit->count; ++i)
		if((acc = FNode_hash(digit->items[i], acc)) == (Py_uhash_t)-1) return -1;
	return acc;
}

static Py_uhash_t FTree_hash(FTree* tree, Py_uhash_t acc) {
	switch(tree->type) {
		case FEmptyT: return acc;
		case FSingleT: return FNode_hash(tree->single, acc);
		case FDeepT: {
			if((acc = FDigit_hash(tree->deep->left, acc)) == (Py_uhash_t)-1) return -1;
			if((acc = FTree_hash(tree->deep->middle, acc)) == (Py_uhash_t)-1) return -1;
			return FDigit_hash(tree->deep->right, acc);
		}
		default: Py_UNREACHABLE();
	}
}

static Py_hash_t PSequence_hash(PSequence* self) {
	Py_uhash_t acc = FTree_hash(self->tree, _PyHASH_XXPRIME_5);
	if(acc == (Py_uhash_t)-1) return -1;
	acc += FTree_ssize(self->tree) ^ (_PyHASH_XXPRIME_5 ^ 3527539UL);
	if (acc == (Py_uhash_t)-1) return 1546275796;
	return acc;
}

// }}}

// {{{ reverse

static FNode* FNode_reverse(FNode* node) {
	if(node->size == 1) return FNode_incRef(node);
	if(node->items[2] == NULL)
		return FNode_make(node->size,
			FNode_reverse(node->items[1]),
			FNode_reverse(node->items[0]), NULL);
	return FNode_make(node->size,
	 	FNode_reverse(node->items[2]),
	 	FNode_reverse(node->items[1]),
		FNode_reverse(node->items[0]));
}

static FDigit* FDigit_reverse(FDigit* digit) {
	switch(digit->count) {
		case 1: return FDigit_make(digit->size, digit->count,
			FNode_reverse(digit->items[0]), NULL, NULL, NULL);
		case 2: return FDigit_make(digit->size, digit->count,
			FNode_reverse(digit->items[1]),
			FNode_reverse(digit->items[0]), NULL, NULL);
		case 3: return FDigit_make(digit->size, digit->count,
			FNode_reverse(digit->items[2]),
			FNode_reverse(digit->items[1]),
			FNode_reverse(digit->items[0]), NULL);
		case 4: return FDigit_make(digit->size, digit->count,
			FNode_reverse(digit->items[3]),
			FNode_reverse(digit->items[2]),
			FNode_reverse(digit->items[1]),
			FNode_reverse(digit->items[0]));
		default: Py_UNREACHABLE();
	}
}

static FTree* FTree_reverse(FTree* tree) {
	switch(tree->type) {
		case FEmptyT: return FEmpty_make();
		case FSingleT: return FSingle_make(
			FNode_reverse(tree->single));
		case FDeepT: return FDeep_make(tree->deep->size,
			FDigit_reverse(tree->deep->right),
			FTree_reverse(tree->deep->middle),
			FDigit_reverse(tree->deep->left));
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_reverse(PSequence* self) {
	return PSequence_make(FTree_reverse(self->tree));
}

// }}}

// {{{ getSlice

static bool FNode_getSlice(FNode* node, FSlice* slice) {
	if(node->size <= slice->modulo) {
		slice->modulo -= node->size;
		return false;
	}
	if(node->size == 1) {
		assert(slice->modulo == 0);
		slice->modulo = slice->step;
		*slice->output++ = FNode_incRef(node);
		return --slice->count == 0;
	}
	if(FNode_getSlice(node->items[0], slice))
		return true;
	if(FNode_getSlice(node->items[1], slice))
		return true;
	if(node->items[2] == NULL)
		return false;
	return FNode_getSlice(node->items[2], slice);
}

static bool FDigit_getSlice(FDigit* digit, FSlice* slice) {
	if(digit->size <= slice->modulo) {
		slice->modulo -= digit->size;
		return false;
	}
	for(int i = 0; i < digit->count; ++i)
		if(FNode_getSlice(digit->items[i], slice))
			return true;
	return false;
}

static bool FTree_getSlice(FTree* tree, FSlice* slice) {
	if(FTree_size(tree) <= slice->modulo) {
		slice->modulo -= FTree_size(tree);
		return false;
	}
	switch(tree->type) {
		case FSingleT:
			return FNode_getSlice(tree->single, slice);
		case FDeepT:
			if(FDigit_getSlice(tree->deep->left, slice))
				return true;
			if(FTree_getSlice(tree->deep->middle, slice))
				return true;
			return FDigit_getSlice(tree->deep->right, slice);
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_getSlice(PSequence* self, PyObject* slice) {
	Py_ssize_t start, stop, step;
	if(PySlice_Unpack(slice, &start, &stop, &step)) return NULL;
	assert(step != 0);
	Py_ssize_t count = PySlice_AdjustIndices(
		FTree_ssize(self->tree), &start, &stop, step);
	if(count == 0)
		return PObj_IncRef(EMPTY_SEQUENCE);
	Py_ssize_t absstep = step > 0 ? step : -step;
	if(step < 0) {
		Py_ssize_t tstart = start + (count - 1) * step;
		stop = start + 1; start = tstart;
	}
	assert(0 < stop && stop <= FTree_ssize(self->tree));
	assert(0 <= start && start < stop);
	FTree* tree;
	if(absstep == 1) {
		tree = FTree_incRef(self->tree);
		if(stop < FTree_ssize(self->tree))
			tree = FTree_decRefRet(tree,
				FTree_takeLeft(tree, stop).tree);
		if(start > 0)
			tree = FTree_decRefRet(tree,
				FTree_takeRight(tree, stop - start).tree);
	} else {
		FNode** nodes = PyMem_Malloc(count * sizeof(PyObject*));
		FSlice slice = {
			.modulo = start,
			.count = count,
			.step = absstep - 1,
			.output = nodes,
		};
		bool sliced UNUSED = FTree_getSlice(self->tree, &slice);
		assert(sliced);
		tree = FTree_fromNodes(count, count, nodes);
		PyMem_Free(nodes);
	}
	if(step < 0)
		tree = FTree_decRefRet(tree, FTree_reverse(tree));
	return PSequence_make(tree);
}

static PyObject* PSequence_subscr(PSequence* self, PyObject* arg) {
	if(PyIndex_Check(arg)) {
		Py_ssize_t index = PyNumber_AsSsize_t(arg, PyExc_IndexError);
		if(index == -1 && PyErr_Occurred()) return NULL;
		return PSequence_getItemS(self, index);
	}
	if(PySlice_Check(arg))
		return (PyObject*)PSequence_getSlice(self, arg);
	return PyErr_Format(PyExc_TypeError,
		"psequence indices must be integers or slices");
}

// }}}

// {{{ deleteSlice

static PSequence* PSequence_deleteSlice(
	PSequence* self,
	PyObject* slice
) {
	Py_ssize_t start, stop, step;
	if(PySlice_Unpack(slice, &start, &stop, &step)) return NULL;
	assert(step != 0);
	Py_ssize_t count = PySlice_AdjustIndices(
		FTree_ssize(self->tree), &start, &stop, step);
	if(count == 0) return PObj_IncRef(self);
	if(step < 0) {
		Py_ssize_t tstart = start + (count - 1) * step;
		stop = start + 1; start = tstart; step = -step;
	}
	assert(0 < stop && stop <= FTree_ssize(self->tree));
	assert(0 <= start && start < stop);
	if(step == 1) {
		PSequence* left = PSequence_takeLeft(self, start);
		PSequence* right = PSequence_takeRight(self,
			FTree_ssize(self->tree) - stop);
		FTree* tree = FTree_extend(left->tree, right->tree);
		Py_DECREF(left); Py_DECREF(right);
		return PSequence_make(tree);
	}
	FSplit splitR = FTree_splitView(self->tree, stop - 1);
	splitR.left = FTree_decRefRet(splitR.left,
		FTree_appendRight(splitR.left, FNode_incRef(splitR.node)));
	FSplit splitL = FTree_splitView(splitR.left, start);
	FTree_decRef(splitR.left);
	FTree* acc = FEmpty_make();
	FTree* rest = splitL.right;
	while(FTree_ssize(rest) >= step) {
		FSplit split = FTree_splitView(rest, step - 1);
		acc = FTree_decRefRet(acc, FTree_decRefRet(split.left,
			FTree_extend(acc, split.left)));
		rest = FTree_decRefRet(rest, split.right);
	}
	acc = FTree_decRefRet(acc, FTree_decRefRet(rest,
		FTree_extend(acc, rest)));
	acc = FTree_decRefRet(acc, FTree_decRefRet(splitL.left,
		FTree_extend(splitL.left, acc)));
	acc = FTree_decRefRet(acc, FTree_decRefRet(splitR.right,
		FTree_extend(acc, splitR.right)));
	return PSequence_make(acc);
}

static PSequence* PSequence_deleteSubscr(PSequence* self, PyObject* index) {
	if(PyIndex_Check(index)) {
		Py_ssize_t idx = PyNumber_AsSsize_t(index, PyExc_IndexError);
		if(idx == -1 && PyErr_Occurred()) return NULL;
		return PSequence_deleteItemS(self, idx);
	}
	if(PySlice_Check(index))
		return PSequence_deleteSlice(self, index);
	return (void*)PyErr_Format(PyExc_TypeError,
		"psequence indices must be integers or slices");
}

// }}}

// {{{ setSlice

static FNode* FNode_setSlice(FNode* node, FSlice* slice) {
	assert(node != NULL);
	if(slice->count == 0)
		return FNode_incRef(node);
	if(node->size <= slice->modulo) {
		slice->modulo -= node->size;
		return FNode_incRef(node);
	}
	if(node->size == 1) {
		assert(slice->modulo == 0);
		slice->modulo = slice->step;
		--slice->count;
		PyObject* value = *(slice->input++);
		return FNode_makeE(PObj_IncRef(value));
	}
	FNode* nodes[3] = { NULL, NULL, NULL };
	nodes[0] = FNode_setSlice(node->items[0], slice);
	nodes[1] = FNode_setSlice(node->items[1], slice);
	if(node->items[2] != NULL)
		nodes[2] = FNode_setSlice(node->items[2], slice);
	return FNode_make(node->size, nodes[0], nodes[1], nodes[2]);
}

static FDigit* FDigit_setSlice(FDigit* digit, FSlice* slice) {
	if(slice->count == 0)
		return FDigit_incRef(digit);
	if(digit->size <= slice->modulo) {
		slice->modulo -= digit->size;
		return FDigit_incRef(digit);
	}
	FNode* nodes[4] = { NULL, NULL, NULL, NULL };
	for(int i = 0; i < digit->count; ++i)
		nodes[i] = FNode_setSlice(digit->items[i], slice);
	return FDigit_makeN(digit->size, digit->count, nodes);
}

static FTree* FTree_setSlice(FTree* tree, FSlice* slice) {
	if(slice->count == 0)
		return FTree_incRef(tree);
	if(FTree_size(tree) <= slice->modulo) {
		slice->modulo -= FTree_size(tree);
		return FTree_incRef(tree);
	}
	switch(tree->type) {
		case FSingleT:
			return FSingle_make(FNode_setSlice(tree->single, slice));
		case FDeepT: {
			FDigit* left = FDigit_setSlice(tree->deep->left, slice);
			FTree* middle = FTree_setSlice(tree->deep->middle, slice);
			FDigit* right = FDigit_setSlice(tree->deep->right, slice);
			return FDeep_make(tree->deep->size, left, middle, right);
		}
		default: Py_UNREACHABLE();
	}
}

static PSequence* PSequence_setSlice(
	PSequence* self,
	PyObject* slice,
	PyObject* value
) {
	Py_ssize_t start, stop, step;
	if(PySlice_Unpack(slice, &start, &stop, &step)) return NULL;
	assert(step != 0);
	Py_ssize_t count = PySlice_AdjustIndices(
		FTree_ssize(self->tree), &start, &stop, step);
	if(step == 1) {
		if(start > stop) stop = start;
		PSequence* mid = PSequence_fromIterable(value);
		PSequence* left = PSequence_takeLeft(self, start);
		PSequence* right = PSequence_takeRight(self,
			FTree_ssize(self->tree) - stop);
		FTree* tree = FTree_extend(mid->tree, right->tree);
		tree = FTree_decRefRet(tree, FTree_extend(left->tree, tree));
		Py_DECREF(mid); Py_DECREF(left); Py_DECREF(right);
		return PSequence_make(tree);
	}
	if(count == 0) return PObj_IncRef(self);
	PyObject* itemsfast = PySequence_Fast(value,
		"must assign iterable to extended slice");
	if(itemsfast == NULL) return NULL;
	if(PySequence_Fast_GET_SIZE(itemsfast) != count) {
		Py_ssize_t size = PySequence_Fast_GET_SIZE(itemsfast);
		Py_DECREF(itemsfast);
		return (void*)PyErr_Format(PyExc_ValueError,
			"attempt to assign sequence of size %zd to"
			" extended slice of size %zd", size, count);
	}
	PyObject** items = PySequence_Fast_ITEMS(itemsfast);
	Py_ssize_t absstep = step > 0 ? step : -step;
	if(step < 0) {
		Py_ssize_t tstart = start + (count - 1) * step;
		stop = start + 1; start = tstart;
		PyObject** buf = PyMem_MALLOC(count * sizeof(PyObject*));
		for(Py_ssize_t i = 0, j = count - 1; i < count; ++i, --j)
			buf[i] = items[j];
		items = buf;
	}
	assert(0 < stop && stop <= FTree_ssize(self->tree));
	assert(0 <= start && start < stop);
	FSlice fslice = {
		.modulo = start,
		.count = count,
		.step = absstep - 1,
		.input = items
	};
	FTree* tree = FTree_setSlice(self->tree, &fslice);
	Py_DECREF(itemsfast);
	if(step < 0) PyMem_FREE(items);
	return PSequence_make(tree);
}

static PSequence* PSequence_setSubscr(
	PSequence* self,
	PyObject* index,
	PyObject* value
) {
	if(PyIndex_Check(index)) {
		Py_ssize_t idx = PyNumber_AsSsize_t(index, PyExc_IndexError);
		if(idx == -1 && PyErr_Occurred()) return NULL;
		return PSequence_setItemS(self, idx, value);
	}
	if(PySlice_Check(index))
		return PSequence_setSlice(self, index, value);
	return (void*)PyErr_Format(PyExc_TypeError,
		"psequence indices must be integers or slices");
}

static PSequence* PSequence_setSubscrN(PSequence* self, PyObject* args) {
	PyObject* index; PyObject* value;
	if(!PyArg_ParseTuple(args, "OO", &index, &value)) return NULL;
	return PSequence_setSubscr(self, index, value);
}

// }}}

// {{{ reduce

static PyObject* PSEQUENCE_FUNCTION = NULL;

static PyObject* PSequence_reduce(PSequence* self) {
	assert(PSEQUENCE_FUNCTION != NULL);
	return Py_BuildValue("(O(N))", PSEQUENCE_FUNCTION, PSequence_toList(self));
}

// }}}

// {{{ transform

static PyObject* TRANSFORM_FUNCTION = NULL;

static PSequence* PSequence_transform(PSequence* self, PyObject* args) {
	if(TRANSFORM_FUNCTION == NULL) {
		PyObject* module = PyImport_ImportModule("pyrsistent._transformations");
		if(module == NULL) return NULL;
		TRANSFORM_FUNCTION = PyObject_GetAttrString(module, "transform");
		Py_DECREF(module);
		if(TRANSFORM_FUNCTION == NULL) return NULL;
	}
	return (PSequence*)PyObject_CallFunctionObjArgs(
		TRANSFORM_FUNCTION, self, args, NULL);
}

// }}}

// {{{ sort

static PSequence* PSequence_sort(
	PSequence*  self,
	PyObject* args,
	PyObject* kwargs
) {
	PSequence* retval = NULL;
	PyObject* list = PSequence_toList(self);
	if(list == NULL) goto err0;
	PyObject* sort = PyObject_GetAttrString(list, "sort");
	if(sort == NULL) goto err1;
	PyObject* sorted = PyObject_Call(sort, args, kwargs);
	if(sorted == NULL) goto err2;
	Py_DECREF(sorted);
	retval = PSequence_fromIterable(list);
	err2: Py_DECREF(sort);
	err1: Py_DECREF(list);
	err0: return retval;
}

// }}}

// {{{ PSequence

static Py_ssize_t PSequence_length(PSequence* self) {
	return FTree_ssize(self->tree);
}

static PyObject* PSequence_refcount(PyObject* self, PyObject* args) {
	return Py_BuildValue("(lll)",
		FRefs_get(FTreeR), FRefs_get(FDigitR), FRefs_get(FNodeR));
}

static PSequenceIter* PSequence_iter(PSequence* self);
static PSequenceIter* PSequence_reversed(PSequence* self);
static PSequenceEvolver* PSequence_evolver(PSequence* self);

static PySequenceMethods PSequence_asSequence = {
	.sq_length         = (lenfunc)PSequence_length,
	.sq_concat         = (binaryfunc)PSequence_extendRight,
	.sq_repeat         = (ssizeargfunc)PSequence_repeat,
	.sq_item           = (ssizeargfunc)PSequence_getItem,
	.sq_ass_item       = (ssizeobjargproc)NULL,
	.sq_contains       = (objobjproc)PSequence_contains,
	.sq_inplace_concat = (binaryfunc)NULL,
	.sq_inplace_repeat = (ssizeargfunc)NULL,
};

static PyMappingMethods PSequence_asMapping = {
	.mp_length        = (lenfunc)PSequence_length,
	.mp_subscript     = (binaryfunc)PSequence_subscr,
	.mp_ass_subscript = (objobjargproc)NULL,
};

#define define_getter(name, func) \
	{ #name, (getter)PSequence_##func, NULL, NULL, NULL }
static PyGetSetDef PSequence_getSet[] = {
	// { (const char*)name, (getter)get, (setter)set, (const char*)doc, (void*)closure }
	define_getter(left, peekLeft),
	define_getter(right, peekRight),
	{NULL}
};
#undef define_getter

#define define_method(name, func, flags) \
	{ #name, (PyCFunction)PSequence_##func, METH_##flags, NULL }
static PyMethodDef PSequence_methods[] = {
	define_method(append,       appendRight,  O),
	define_method(appendright,  appendRight,  O),
	define_method(appendleft,   appendLeft,   O),
	define_method(view,         view,         VARARGS),
	define_method(viewright,    viewRight,    NOARGS),
	define_method(viewleft,     viewLeft,     NOARGS),
	define_method(splitat,      splitAt,      O),
	define_method(extend,       extendRight,  O),
	define_method(extendright,  extendRight,  O),
	define_method(extendleft,   extendLeft,   O),
	define_method(reverse,      reverse,      NOARGS),
	define_method(__reversed__, reversed,     NOARGS),
	define_method(set,          setSubscrN,   VARARGS),
	define_method(mset,         msetItemN,    VARARGS),
	define_method(insert,       insertItemN,  VARARGS),
	define_method(delete,       deleteSubscr, O),
	define_method(remove,       removeItemN,  O),
	define_method(transform,    transform,    VARARGS),
	define_method(index,        indexItem,    O),
	define_method(count,        countItem,    O),
	define_method(chunksof,     chunksOfN,    O),
	define_method(__reduce__,   reduce,       NOARGS),
	define_method(evolver,      evolver,      NOARGS),
	define_method(tolist,       toList,       NOARGS),
	define_method(totuple,      toTuple,      NOARGS),
	define_method(_totree,      toTree,       NOARGS),
	define_method(sort,         sort,         VARARGS | METH_KEYWORDS),
	define_method(_fromtree,    fromTuple,    O       | METH_STATIC),
	define_method(_refcount,    refcount,     NOARGS  | METH_STATIC),
	{NULL}
};
#undef define_method

static PyTypeObject PSequenceType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name              = (const char*)"pyrsistent._psequence._c_ext.PSequence",
	.tp_basicsize         = (Py_ssize_t)sizeof(PSequence),
	.tp_itemsize          = (Py_ssize_t)0,
	.tp_dealloc           = (destructor)PSequence_dealloc,
	.tp_vectorcall_offset = (Py_ssize_t)0,
	.tp_getattr           = (getattrfunc)NULL,
	.tp_setattr           = (setattrfunc)NULL,
	.tp_as_async          = (PyAsyncMethods*)NULL,
	.tp_repr              = (reprfunc)PSequence_repr,
	.tp_as_number         = (PyNumberMethods*)NULL,
	.tp_as_sequence       = (PySequenceMethods*)&PSequence_asSequence,
	.tp_as_mapping        = (PyMappingMethods*)&PSequence_asMapping,
	.tp_hash              = (hashfunc)PSequence_hash,
	.tp_call              = (ternaryfunc)NULL,
	.tp_str               = (reprfunc)NULL,
	.tp_getattro          = (getattrofunc)NULL,
	.tp_setattro          = (setattrofunc)NULL,
	.tp_as_buffer         = (PyBufferProcs*)NULL,
	.tp_flags             = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
	.tp_doc               = (const char*)NULL,
	.tp_traverse          = (traverseproc)PSequence_traverse,
	.tp_clear             = (inquiry)NULL,
	.tp_richcompare       = (richcmpfunc)PSequence_compare,
	.tp_weaklistoffset    = (Py_ssize_t)offsetof(PSequence, weakrefs),
	.tp_iter              = (getiterfunc)PSequence_iter,
	.tp_iternext          = (iternextfunc)NULL,
	.tp_methods           = (struct PyMethodDef*)PSequence_methods,
	.tp_members           = (struct PyMemberDef*)NULL,
	.tp_getset            = (struct PyGetSetDef*)PSequence_getSet,
	.tp_base              = (PyTypeObject*)NULL,
	.tp_dict              = (PyObject*)NULL,
	.tp_descr_get         = (descrgetfunc)NULL,
	.tp_descr_set         = (descrsetfunc)NULL,
	.tp_dictoffset        = (Py_ssize_t)0,
	.tp_init              = (initproc)NULL,
	.tp_alloc             = (allocfunc)NULL,
	.tp_new               = (newfunc)NULL,
	.tp_free              = (freefunc)NULL,
	.tp_is_gc             = (inquiry)NULL,
	.tp_bases             = (PyObject*)NULL,
	.tp_mro               = (PyObject*)NULL,
	.tp_cache             = (PyObject*)NULL,
	.tp_subclasses        = (PyObject*)NULL,
	.tp_weaklist          = (PyObject*)NULL,
	.tp_del               = (destructor)NULL,
	.tp_version_tag       = (unsigned int)0,
	.tp_finalize          = (destructor)NULL,
	.tp_vectorcall        = (vectorcallfunc)NULL,
};

// }}}

// {{{ iter next

static FIter* FIter_pushStack(
	FIter* iter,
	FIterT type,
	int index,
	void* item
) {
	return FIter_make(type, index, item, iter);
}

static FIter* FIter_swapStack(
	FIter* iter,
	FIterT type,
	int index,
	void* item
) {
	FIter_decRef(iter);
	iter->type = type;
	iter->index = index;
	iter->tree = item;
	FIter_incRef(iter);
	return iter;
}

static FIter* FIter_popStack(FIter* iter) {
	assert(iter != NULL);
	FIter* next = iter->next;
	FIter_dealloc(iter, false);
	return next;
}

static FIter* FIter_nextStack(FIter* iter) {
	if(iter == NULL) return iter;
	switch(iter->type) {
		case FTreeI:
			switch(iter->tree->type) {
				case FEmptyT:
					assert(iter->index == 0);
					return FIter_nextStack(FIter_popStack(iter));
				case FSingleT:
					assert(iter->index == 0);
					return FIter_nextStack(FIter_swapStack(
						iter, FNodeI, 0, iter->tree->single));
				case FDeepT:
					switch(iter->index++) {
						case 0: return FIter_nextStack(FIter_pushStack(
							iter, FDigitI, 0, iter->tree->deep->left));
						case 1: return FIter_nextStack(FIter_pushStack(
							iter, FTreeI, 0, iter->tree->deep->middle));
						case 2: return FIter_nextStack(FIter_swapStack(
							iter, FDigitI, 0, iter->tree->deep->right));
						default: Py_UNREACHABLE();
					}
				default: Py_UNREACHABLE();
			};
		case FDigitI: {
			assert(0 <= iter->index && iter->index <= 4);
			FNode* node = iter->digit->items[iter->index];
			if(++iter->index == iter->digit->count)
				return FIter_nextStack(FIter_swapStack(iter, FNodeI, 0, node));
			return FIter_nextStack(FIter_pushStack(iter, FNodeI, 0, node));
		}
		case FNodeI: {
			if(iter->node->size == 1) {
				assert(iter->index == 0);
				return iter;
			}
			assert(0 <= iter->index &&
				iter->index <= FNode_count(iter->node));
			FNode* node = iter->node->items[iter->index];
			if(++iter->index == FNode_count(iter->node))
				return FIter_nextStack(FIter_swapStack(iter, FNodeI, 0, node));
			return FIter_nextStack(FIter_pushStack(iter, FNodeI, 0, node));
		}
		default: Py_UNREACHABLE();
	}
}

static FIter* FIter_prevStack(FIter* iter) {
	if(iter == NULL) return iter;
	switch(iter->type) {
		case FTreeI:
			switch(iter->tree->type) {
				case FEmptyT:
					assert(iter->index == 0);
					return FIter_prevStack(FIter_popStack(iter));
				case FSingleT: {
					assert(iter->index == 1);
					FNode* node = iter->tree->single;
					return FIter_prevStack(FIter_swapStack(
						iter, FNodeI, FNode_count(node), node));
				}
				case FDeepT:
					switch(iter->index--) {
						case 1: {
							FDigit* digit = iter->tree->deep->left;
							return FIter_prevStack(FIter_swapStack(
								iter, FDigitI, digit->count, digit));
						}
						case 2: {
							FTree* tree = iter->tree->deep->middle;
							switch(tree->type) {
								case FEmptyT: return FIter_prevStack(FIter_pushStack(
									iter, FTreeI, 0, tree));
								case FSingleT: return FIter_prevStack(FIter_pushStack(
									iter, FTreeI, 1, tree));
								case FDeepT: return FIter_prevStack(FIter_pushStack(
									iter, FTreeI, 3, tree));
								default: Py_UNREACHABLE();
							}
						}
						case 3: {
							FDigit* digit = iter->tree->deep->right;
							return FIter_prevStack(FIter_pushStack(
								iter, FDigitI, digit->count, digit));
						}
						default: Py_UNREACHABLE();
					}
				default: Py_UNREACHABLE();
			};
		case FDigitI: {
			assert(1 <= iter->index && iter->index <= 4);
			FNode* node = iter->digit->items[--iter->index];
			if(iter->index == 0)
				return FIter_prevStack(FIter_swapStack(
					iter, FNodeI, FNode_count(node), node));
			return FIter_prevStack(FIter_pushStack(
				iter, FNodeI, FNode_count(node), node));
		}
		case FNodeI: {
			if(iter->node->size == 1) {
				assert(iter->index == 1);
				return iter;
			}
			assert(1 <= iter->index &&
				iter->index <= FNode_count(iter->node));
			FNode* node = iter->node->items[--iter->index];
			if(iter->index == 0)
				return FIter_prevStack(FIter_swapStack(
					iter, FNodeI, FNode_count(node), node));
			return FIter_prevStack(FIter_pushStack(
				iter, FNodeI, FNode_count(node), node));
		}
		default: Py_UNREACHABLE();
	}
}

static PyObject* PSequenceIter_next(PSequenceIter* self) {
	if(self->reverse)
		self->stack = FIter_prevStack(self->stack);
	else
		self->stack = FIter_nextStack(self->stack);
	if(self->stack == NULL) {
		if(self->reverse)
			assert(self->index == 0);
		else
			assert(self->index == FTree_ssize(self->seq->tree));
		return NULL;
	}
	if(self->reverse)
		--self->index;
	else
		++self->index;
	assert(0 <= self->index &&
		self->index <= FTree_ssize(self->seq->tree));
	assert(self->stack->type == FNodeI);
	assert(self->stack->node->size == 1);
	PyObject* value = PObj_IncRef(self->stack->node->value);
	self->stack = FIter_popStack(self->stack);
	return value;
}

// }}}

// {{{ PSequenceIter

static PSequenceIter* PSequence_iter(PSequence* self) {
	return PSequenceIter_make(
		0, false, PObj_IncRef(self),
		FIter_make(FTreeI, 0, self->tree, NULL));
}

static PSequenceIter* PSequence_reversed(PSequence* self) {
	int index;
	switch(self->tree->type) {
		case FEmptyT: index = 0; break;
		case FSingleT: index = 1; break;
		case FDeepT: index = 3; break;
		default: Py_UNREACHABLE();
	}
	return PSequenceIter_make(
		FTree_size(self->tree), true, PObj_IncRef(self),
		FIter_make(FTreeI, index, self->tree, NULL));
}

static PyObject* PSequenceIter_lenHint(PSequenceIter* self) {
	return PyLong_FromSsize_t(self->reverse ? self->index
		: FTree_ssize(self->seq->tree) - self->index);
}

static int PSequenceIter_traverse(
	PSequenceIter *self,
	visitproc visit,
	void* arg
) {
	return PSequence_traverse(self->seq, visit, arg);
}

#define define_method(name, method, flags) \
	{ #name, (PyCFunction)PSequenceIter_##method, METH_##flags, NULL }
static PyMethodDef PSequenceIter_methods[] = {
	define_method(__length_hint__, lenHint, NOARGS),
	{NULL}
};
#undef define_method

static PyTypeObject PSequenceIterType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name              = (const char*)"pyrsistent._psequence._c_ext.Iterator",
	.tp_basicsize         = (Py_ssize_t)sizeof(PSequenceIter),
	.tp_itemsize          = (Py_ssize_t)0,
	.tp_dealloc           = (destructor)PSequenceIter_dealloc,
	.tp_vectorcall_offset = (Py_ssize_t)0,
	.tp_getattr           = (getattrfunc)NULL,
	.tp_setattr           = (setattrfunc)NULL,
	.tp_as_async          = (PyAsyncMethods*)NULL,
	.tp_repr              = (reprfunc)NULL,
	.tp_as_number         = (PyNumberMethods*)NULL,
	.tp_as_sequence       = (PySequenceMethods*)NULL,
	.tp_as_mapping        = (PyMappingMethods*)NULL,
	.tp_hash              = (hashfunc)NULL,
	.tp_call              = (ternaryfunc)NULL,
	.tp_str               = (reprfunc)NULL,
	.tp_getattro          = (getattrofunc)PyObject_GenericGetAttr,
	.tp_setattro          = (setattrofunc)NULL,
	.tp_as_buffer         = (PyBufferProcs*)NULL,
	.tp_flags             = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
	.tp_doc               = (const char*)NULL,
	.tp_traverse          = (traverseproc)PSequenceIter_traverse,
	.tp_clear             = (inquiry)NULL,
	.tp_richcompare       = (richcmpfunc)NULL,
	.tp_weaklistoffset    = (Py_ssize_t)0,
	.tp_iter              = (getiterfunc)PyObject_SelfIter,
	.tp_iternext          = (iternextfunc)PSequenceIter_next,
	.tp_methods           = (struct PyMethodDef*)PSequenceIter_methods,
	.tp_members           = (struct PyMemberDef*)NULL,
	.tp_getset            = (struct PyGetSetDef*)NULL,
	.tp_base              = (PyTypeObject*)NULL,
	.tp_dict              = (PyObject*)NULL,
	.tp_descr_get         = (descrgetfunc)NULL,
	.tp_descr_set         = (descrsetfunc)NULL,
	.tp_dictoffset        = (Py_ssize_t)0,
	.tp_init              = (initproc)NULL,
	.tp_alloc             = (allocfunc)NULL,
	.tp_new               = (newfunc)NULL,
	.tp_free              = (freefunc)NULL,
	.tp_is_gc             = (inquiry)NULL,
	.tp_bases             = (PyObject*)NULL,
	.tp_mro               = (PyObject*)NULL,
	.tp_cache             = (PyObject*)NULL,
	.tp_subclasses        = (PyObject*)NULL,
	.tp_weaklist          = (PyObject*)NULL,
	.tp_del               = (destructor)NULL,
	.tp_version_tag       = (unsigned int)0,
	.tp_finalize          = (destructor)NULL,
	.tp_vectorcall        = (vectorcallfunc)NULL,
};

// }}}

// {{{ evolver inherit

#define inherit_query0(name, rettype) \
	static rettype PSequenceEvolver_##name \
	(PSequenceEvolver* self) \
	{ return PSequence_##name(self->seq); }
#define inherit_query1(name, rettype, type1) \
	static rettype PSequenceEvolver_##name \
	(PSequenceEvolver* self, type1 arg1) \
	{ return PSequence_##name(self->seq, arg1); }
#define inherit_query2(name, rettype, type1, type2) \
	static rettype PSequenceEvolver_##name \
	(PSequenceEvolver* self, type1 arg1, type2 arg2) \
	{ return PSequence_##name(self->seq, arg1, arg2); }

#define inherit_method0(name) \
	static PSequenceEvolver* PSequenceEvolver_##name \
	(PSequenceEvolver* self) \
	{ PSequence* seq = PSequence_##name(self->seq); \
		if(seq == NULL) return NULL; \
		Py_DECREF(self->seq); self->seq = seq; return PObj_IncRef(self); }
#define inherit_method1(name, type1) \
	static PSequenceEvolver* PSequenceEvolver_##name \
	(PSequenceEvolver* self, type1 arg1) \
	{ PSequence* seq = PSequence_##name(self->seq, arg1); \
		if(seq == NULL) return NULL; \
		Py_DECREF(self->seq); self->seq = seq; return PObj_IncRef(self); }
#define inherit_method2(name, type1, type2) \
	static PSequenceEvolver* PSequenceEvolver_##name \
	(PSequenceEvolver* self, type1 arg1, type2 arg2) \
	{ PSequence* seq = PSequence_##name(self->seq, arg1, arg2); \
		if(seq == NULL) return NULL; \
		Py_DECREF(self->seq); self->seq = seq; return PObj_IncRef(self); }
#define inherit_methodN(name) \
	static PSequenceEvolver* PSequenceEvolver_##name \
	(PSequenceEvolver* self, PyObject* args) \
	{ PSequence* seq = PSequence_##name(self->seq, args); \
		if(seq == NULL) return NULL; \
		Py_DECREF(self->seq); self->seq = seq; return PObj_IncRef(self); }

#define inherit_new1(name, type1) \
	static PSequenceEvolver* PSequenceEvolver_##name##New \
	(PSequenceEvolver* self, type1 arg1) \
	{ PSequence* seq = PSequence_##name(self->seq, arg1); \
		if(seq == NULL) return NULL; \
		return PSequenceEvolver_make(seq); }

inherit_query0(length, Py_ssize_t)
inherit_method1(repeat, Py_ssize_t)
inherit_new1(repeat, Py_ssize_t)

inherit_query1(getItem, PyObject*, Py_ssize_t)
inherit_query1(subscr, PyObject*, PyObject*)

inherit_methodN(appendRight)
inherit_methodN(appendLeft)
inherit_query1(peekRight, PyObject*, void*)
inherit_query1(peekLeft, PyObject*, void*)

inherit_query0(viewRight, PyObject*)
inherit_query0(viewLeft, PyObject*)
inherit_query1(view, PyObject*, PyObject*)

inherit_query1(splitAt, PyObject*, PyObject*)
inherit_query1(chunksOfN, PSequence*, PyObject*)

inherit_methodN(extendLeft)
inherit_methodN(extendRight)
inherit_new1(extendRight, PyObject*)

inherit_method0(reverse)
inherit_query0(reversed, PSequenceIter*)

inherit_methodN(setSubscrN)
inherit_methodN(msetItemN)
inherit_methodN(insertItemN)
inherit_methodN(deleteSubscr)
inherit_methodN(removeItemN)

inherit_query1(indexItem, PyObject*, PyObject*)
inherit_query1(countItem, PyObject*, PyObject*)
inherit_query1(contains, int, PyObject*)

inherit_query0(toList, PyObject*)
inherit_query0(toTuple, PyObject*)
inherit_query0(toTree, PyObject*)

inherit_method2(sort, PyObject*, PyObject*)
inherit_query0(reduce, PyObject*)
inherit_query2(traverse, int, visitproc, void*)
inherit_query0(iter, PSequenceIter*)
inherit_methodN(transform)

#undef inherit_query0
#undef inherit_query1
#undef inherit_query2
#undef inherit_method0
#undef inherit_method1
#undef inherit_methodN
#undef inherit_new1

// }}}

// {{{ pop

static PyObject* PSequenceEvolver_popLeft(PSequenceEvolver* self) {
	if(FTree_empty(self->seq->tree))
		return (void*)PyErr_Format(PyExc_IndexError,
			"pop from empty sequence");
	FView view = FTree_viewLeft(self->seq->tree);
	assert(view.node->size == 1);
	Py_DECREF(self->seq);
	self->seq = PSequence_make(view.tree);
	return PObj_IncRef(view.node->value);
}

static PyObject* PSequenceEvolver_popRight(PSequenceEvolver* self) {
	if(FTree_empty(self->seq->tree))
		return (void*)PyErr_Format(PyExc_IndexError,
			"pop from empty sequence");
	FView view = FTree_viewRight(self->seq->tree);
	assert(view.node->size == 1);
	Py_DECREF(self->seq);
	self->seq = PSequence_make(view.tree);
	return PObj_IncRef(view.node->value);
}

static PyObject* PSequenceEvolver_pop(PSequenceEvolver* self, PyObject* args) {
	PyObject* arg = NULL;
	if(!PyArg_ParseTuple(args, "|O", &arg)) return NULL;
	if(arg == NULL) return PSequenceEvolver_popRight(self);
	PyObject* value = PSequenceEvolver_subscr(self, arg);
	if(value == NULL) return NULL;
	PSequenceEvolver* del = PSequenceEvolver_deleteSubscr(self, arg);
	if(del == NULL) { Py_DECREF(value); return NULL; }
	Py_DECREF(del);
	return value;
}

// }}}

// {{{ PSequenceEvolver

static PSequenceEvolver* PSequence_evolver(PSequence* self) {
	return PSequenceEvolver_make(PObj_IncRef(self));
}

static PyObject* PSequenceEvolver_repr(PSequenceEvolver* self) {
	PyObject* list = PSequence_toList(self->seq);
	if(list == NULL) return NULL;
	PyObject* repr = PyObject_Repr(list);
	Py_DECREF(list);
	if(repr == NULL) return NULL;
	PyObject* form = PyUnicode_FromFormat("%s%U%s",
		"psequence(", repr, ").evolver()");
	Py_DECREF(repr);
	return form;
}

static PSequence* PSequenceEvolver_persistent(PSequenceEvolver* self) {
	return PObj_IncRef(self->seq);
}

static PSequenceEvolver* PSequenceEvolver_copy(PSequenceEvolver* self) {
	return PSequenceEvolver_make(PObj_IncRef(self->seq));
}

static PSequenceEvolver* PSequenceEvolver_clear(PSequenceEvolver* self) {
	Py_DECREF(self->seq);
	self->seq = PObj_IncRef(EMPTY_SEQUENCE);
	return PObj_IncRef(Py_None);
}

static int PSequenceEvolver_assItem(
	PSequenceEvolver* self,
	Py_ssize_t index,
	PyObject* value
) {
	PSequence* seq;
	if(value == NULL)
		seq = PSequence_deleteItem(self->seq, index);
	else
		seq = PSequence_setItem(self->seq, index, value);
	if(seq == NULL) return -1;
	Py_DECREF(self->seq);
	self->seq = seq;
	return 0;
}

static int PSequenceEvolver_assSubscr(
	PSequenceEvolver* self,
	PyObject* index,
	PyObject* value
) {
	PSequence* seq;
	if(value == NULL)
		seq = PSequence_deleteSubscr(self->seq, index);
	else
		seq = PSequence_setSubscr(self->seq, index, value);
	if(seq == NULL) return -1;
	Py_DECREF(self->seq);
	self->seq = seq;
	return 0;
}

#define define_getter(name, func) \
	{ #name, (getter)PSequenceEvolver_##func, NULL, NULL, NULL }
static PyGetSetDef PSequenceEvolver_getSet[] = {
	// { (const char*)name, (getter)get, (setter)set, (const char*)doc, (void*)closure }
	define_getter(left, peekLeft),
	define_getter(right, peekRight),
	{NULL}
};
#undef define_getter

#define define_method(name, method, flags) \
	{ #name, (PyCFunction)PSequenceEvolver_##method, METH_##flags, NULL }
static PyMethodDef PSequenceEvolver_methods[] = {
	define_method(append,       appendRight,  O),
	define_method(appendright,  appendRight,  O),
	define_method(appendleft,   appendLeft,   O),
	define_method(view,         view,         VARARGS),
	define_method(viewright,    viewRight,    NOARGS),
	define_method(viewleft,     viewLeft,     NOARGS),
	define_method(pop,          pop,          VARARGS),
	define_method(popright,     popRight,     NOARGS),
	define_method(popleft,      popLeft,      NOARGS),
	define_method(splitat,      splitAt,      O),
	define_method(extend,       extendRight,  O),
	define_method(extendright,  extendRight,  O),
	define_method(extendleft,   extendLeft,   O),
	define_method(reverse,      reverse,      NOARGS),
	define_method(__reversed__, reversed,     NOARGS),
	define_method(set,          setSubscrN,   VARARGS),
	define_method(mset,         msetItemN,    VARARGS),
	define_method(insert,       insertItemN,  VARARGS),
	define_method(delete,       deleteSubscr, O),
	define_method(remove,       removeItemN,  O),
	define_method(transform,    transform,    VARARGS),
	define_method(index,        indexItem,    O),
	define_method(count,        countItem,    O),
	define_method(chunksof,     chunksOfN,    O),
	define_method(__reduce__,   reduce,       NOARGS),
	define_method(persistent,   persistent,   NOARGS),
	define_method(tolist,       toList,       NOARGS),
	define_method(totuple,      toTuple,      NOARGS),
	define_method(_totree,      toTree,       NOARGS),
	define_method(copy,         copy,         NOARGS),
	define_method(clear,        clear,        NOARGS),
	define_method(sort,         sort,         VARARGS | METH_KEYWORDS),
	{NULL}
};
#undef define_method

static PySequenceMethods PSequenceEvolver_asSequence = {
	.sq_length         = (lenfunc)PSequenceEvolver_length,
	.sq_concat         = (binaryfunc)PSequenceEvolver_extendRightNew,
	.sq_repeat         = (ssizeargfunc)PSequenceEvolver_repeatNew,
	.sq_item           = (ssizeargfunc)PSequenceEvolver_getItem,
	.sq_ass_item       = (ssizeobjargproc)PSequenceEvolver_assItem,
	.sq_contains       = (objobjproc)PSequenceEvolver_contains,
	.sq_inplace_concat = (binaryfunc)PSequenceEvolver_extendRight,
	.sq_inplace_repeat = (ssizeargfunc)PSequenceEvolver_repeat,
};

static PyMappingMethods PSequenceEvolver_asMapping = {
	.mp_length        = (lenfunc)PSequenceEvolver_length,
	.mp_subscript     = (binaryfunc)PSequenceEvolver_subscr,
	.mp_ass_subscript = (objobjargproc)PSequenceEvolver_assSubscr,
};

static PyTypeObject PSequenceEvolverType = {
	PyVarObject_HEAD_INIT(NULL, 0)
	.tp_name              = (const char*)"pyrsistent._psequence._c_ext.Iterator",
	.tp_basicsize         = (Py_ssize_t)sizeof(PSequenceEvolver),
	.tp_itemsize          = (Py_ssize_t)0,
	.tp_dealloc           = (destructor)PSequenceEvolver_dealloc,
	.tp_vectorcall_offset = (Py_ssize_t)0,
	.tp_getattr           = (getattrfunc)NULL,
	.tp_setattr           = (setattrfunc)NULL,
	.tp_as_async          = (PyAsyncMethods*)NULL,
	.tp_repr              = (reprfunc)PSequenceEvolver_repr,
	.tp_as_number         = (PyNumberMethods*)NULL,
	.tp_as_sequence       = (PySequenceMethods*)&PSequenceEvolver_asSequence,
	.tp_as_mapping        = (PyMappingMethods*)&PSequenceEvolver_asMapping,
	.tp_hash              = (hashfunc)NULL,
	.tp_call              = (ternaryfunc)NULL,
	.tp_str               = (reprfunc)NULL,
	.tp_getattro          = (getattrofunc)PyObject_GenericGetAttr,
	.tp_setattro          = (setattrofunc)NULL,
	.tp_as_buffer         = (PyBufferProcs*)NULL,
	.tp_flags             = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_HAVE_GC,
	.tp_doc               = (const char*)NULL,
	.tp_traverse          = (traverseproc)PSequenceEvolver_traverse,
	.tp_clear             = (inquiry)NULL,
	.tp_richcompare       = (richcmpfunc)PSequence_compare,
	.tp_weaklistoffset    = (Py_ssize_t)0,
	.tp_iter              = (getiterfunc)PSequenceEvolver_iter,
	.tp_iternext          = (iternextfunc)NULL,
	.tp_methods           = (struct PyMethodDef*)PSequenceEvolver_methods,
	.tp_members           = (struct PyMemberDef*)NULL,
	.tp_getset            = (struct PyGetSetDef*)PSequenceEvolver_getSet,
	.tp_base              = (PyTypeObject*)NULL,
	.tp_dict              = (PyObject*)NULL,
	.tp_descr_get         = (descrgetfunc)NULL,
	.tp_descr_set         = (descrsetfunc)NULL,
	.tp_dictoffset        = (Py_ssize_t)0,
	.tp_init              = (initproc)NULL,
	.tp_alloc             = (allocfunc)NULL,
	.tp_new               = (newfunc)NULL,
	.tp_free              = (freefunc)NULL,
	.tp_is_gc             = (inquiry)NULL,
	.tp_bases             = (PyObject*)NULL,
	.tp_mro               = (PyObject*)NULL,
	.tp_cache             = (PyObject*)NULL,
	.tp_subclasses        = (PyObject*)NULL,
	.tp_weaklist          = (PyObject*)NULL,
	.tp_del               = (destructor)NULL,
	.tp_version_tag       = (unsigned int)0,
	.tp_finalize          = (destructor)NULL,
	.tp_vectorcall        = (vectorcallfunc)NULL,
};

// }}}

// {{{ module def

static PSequence* pyrsistent_psequence(PyObject* self, PyObject* args) {
	PyObject* arg = NULL;
	if(!PyArg_ParseTuple(args, "|O", &arg)) return NULL;
	if(arg == NULL) return PObj_IncRef(EMPTY_SEQUENCE);
	return PSequence_fromIterable(arg);
}

#define define_method(name, method, flags) \
	{ #name, (PyCFunction)pyrsistent_##method, METH_##flags, NULL }
static PyMethodDef methodDef[] = {
	define_method(psequence, psequence, VARARGS),
	{NULL}
};
#undef define_method

static struct PyModuleDef moduleDef = {
	PyModuleDef_HEAD_INIT,
	.m_name     = (const char*)"pyrsistent._psequence._c_ext",
	.m_doc      = (const char*)"persistent sequence c implementation",
	.m_size     = (Py_ssize_t)-1,
	.m_methods  = (PyMethodDef*)methodDef,
	.m_slots    = (struct PyModuleDef_Slot*)NULL,
	.m_traverse = (traverseproc)NULL,
	.m_clear    = (inquiry)NULL,
	.m_free     = (freefunc)NULL,
};

void* PObj_getDoc(const char* name, PyObject* base) {
	void* retval = NULL;
	PyObject* method = PyObject_GetAttrString(base, name);
	if(method == NULL) goto err0;
	PyObject* docstring = PyObject_GetAttrString(method, "__doc__");
	if(docstring == NULL) goto err1;
	if(!PyUnicode_Check(docstring) || PyUnicode_READY(docstring) == -1) {
		PyErr_Format(PyExc_TypeError,
			"expected __doc__ of %R to be a string", method);
		goto err2;
	}
	retval = PyUnicode_DATA(docstring);
	err2: Py_DECREF(docstring);
	err1: Py_DECREF(method);
	err0: return retval;
}

bool pyrsistent_psequence_inheritDocs() {
	bool okay = false;

	PyObject* module = PyImport_ImportModule("pyrsistent._psequence._base");
	if(module == NULL) goto err0;

	PyObject* seqbase = PyObject_GetAttrString(module, "PSequenceBase");
	if(seqbase == NULL) goto err1;
	if(PSequenceType.tp_doc == NULL)
		PSequenceType.tp_doc = PObj_getDoc("PSequenceBase", module);
	if(PSequenceType.tp_doc == NULL) goto err1;

	for(struct PyMethodDef* methdef = PSequenceType.tp_methods;
			methdef->ml_name != NULL; ++methdef) {
		if(methdef->ml_doc != NULL || methdef->ml_name[0] == '_') continue;
		methdef->ml_doc = PObj_getDoc(methdef->ml_name, seqbase);
		if(methdef->ml_doc == NULL) goto err2;
	}

	for(struct PyGetSetDef* methdef = PSequenceType.tp_getset;
			methdef->name != NULL; ++methdef) {
		if(methdef->doc != NULL || methdef->name[0] == '_') continue;
		methdef->doc = PObj_getDoc(methdef->name, seqbase);
		if(methdef->doc == NULL) goto err2;
	}

	PyObject* evobase = PyObject_GetAttrString(module, "PSequenceEvolverBase");
	if(evobase == NULL) goto err2;
	if(PSequenceType.tp_doc == NULL)
		PSequenceType.tp_doc = PObj_getDoc("PSequenceEvolverBase", module);
	if(PSequenceType.tp_doc == NULL) goto err1;

	for(struct PyMethodDef* methdef = PSequenceEvolverType.tp_methods;
			methdef->ml_name != NULL; ++methdef) {
		if(methdef->ml_doc != NULL || methdef->ml_name[0] == '_') continue;
		methdef->ml_doc = PObj_getDoc(methdef->ml_name, evobase);
		if(methdef->ml_doc == NULL) goto err3;
	}

	for(struct PyGetSetDef* methdef = PSequenceEvolverType.tp_getset;
			methdef->name != NULL; ++methdef) {
		if(methdef->doc != NULL || methdef->name[0] == '_') continue;
		methdef->doc = PObj_getDoc(methdef->name, evobase);
		if(methdef->doc == NULL) goto err3;
	}

	okay = true;
	err3: Py_DECREF(evobase);
	err2: Py_DECREF(seqbase);
	err1: Py_DECREF(module);
	err0: return okay;
}

PyMODINIT_FUNC PyInit__c_ext() {
	if(!pyrsistent_psequence_inheritDocs()) return NULL;

	if(PyType_Ready(&PSequenceType) < 0) return NULL;
	if(PyType_Ready(&PSequenceIterType) < 0) return NULL;
	if(PyType_Ready(&PSequenceEvolverType) < 0) return NULL;

	if(EMPTY_SEQUENCE == NULL) {
		EMPTY_SEQUENCE = PyObject_GC_New(PSequence, &PSequenceType);
		if(EMPTY_SEQUENCE == NULL) return NULL;
		EMPTY_SEQUENCE->tree = FEmpty_make();
		EMPTY_SEQUENCE->weakrefs = NULL;
		PyObject_GC_Track((PyObject*)EMPTY_SEQUENCE);
	}

	PyObject* module = PyModule_Create(&moduleDef);
	if(module == NULL) return NULL;
	PyModule_AddObject(module, "PSequence", PObj_IncRef(&PSequenceType));
	PyModule_AddObject(module, "Evolver", PObj_IncRef(&PSequenceEvolverType));
	PSEQUENCE_FUNCTION = PyObject_GetAttrString(module, "psequence");
	assert(PSEQUENCE_FUNCTION != NULL);
	return module;
}

// }}}

// vim: set foldmethod=marker foldlevel=0 nocindent:
