#include <stdio.h>
#include <string.h>
#include "Python.h"

static PyObject *csnmpsim_compareOids(PyObject *self, PyObject *args) {
    char *oid1, *oid2; 
    int i, l1, l2, smaller, start1, start2, end1, end2, val1, val2;
    char tmp1, tmp2;

    if (!PyArg_ParseTuple(args, "ss", &oid1, &oid2)) {
        return NULL;
    }
    l1 = strlen(oid1);
    l2 = strlen(oid2);
    if (l1 > l2)
        smaller = l2;
    else
        smaller = l1;
    for (i=0; i < smaller; i++) {
        if (oid1[i] == oid2[i]) {
            continue;
        }
        // Found difference. Grab chars up to next and then compare numerically
        start1 = start2 = i;
        while (oid1[start1-1] != '.')
            start1--;
        while (oid2[start2-1] != '.')
            start2--;
        end1 = i;
        end2 = i;
        while (end1 < l1 && oid1[end1] != '.')
            end1++; 
        while (end2 < l2 && oid2[end2] != '.')
            end2++; 
        // Now convert to ints and compare (note: this is a bit weird. We want to pass
        // strings to atoi, but we don't want to allocate new ones. Add nulls in right
        // places to have strings terminated, but then undo this after since we're
        // changing the actual python strings.
        tmp1 = oid1[end1];
        tmp2 = oid2[end2];
        oid1[end1] = 0;
        oid2[end2] = 0;
        val1 = atoi(&oid1[start1]);
        val2 = atoi(&oid2[start2]);
        oid1[end1] = tmp1;
        oid2[end2] = tmp2;

        // Then compare
        if (val1 < val2) 
            // First oid comes first
            return Py_BuildValue("i", -1);
        else if (val1 > val2)
            // Second oid comes first
            return Py_BuildValue("i", 1);
    }
    if (l1 == l2) {
        // They are the same
        return Py_BuildValue("i", 0);
    }
    else  {
        // One's a substring of the other. The shorter comes first.
        if (l1 < l2) {
            return Py_BuildValue("i", -1);
        }
        else {
            return Py_BuildValue("i", 1);
        }
    }
}

static PyMethodDef methods[] = {
    {"compareOids",  csnmpsim_compareOids, METH_VARARGS},
    {NULL,        NULL}        // Sentinel
};

void initcsnmpsim() {
    (void) Py_InitModule("csnmpsim", methods);
}
