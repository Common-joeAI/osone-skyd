#include <stdio.h>
#include <stdlib.h>

// Function to simulate resource management
void* try_alloc(void) {
    void* ptr = malloc(sizeof(int));
    if (ptr == NULL) {
        __asm__ __volatile__("movl %0, %%eax" :: "r"(1)); // exit with code 1 on failure
        return NULL;
    }
    *ptr = 42; // simulate successful allocation
    return ptr;
}

int try_free(void* ptr) {
    if (ptr != NULL) {
        free(ptr);
        return 0; // success
    } else {
        __asm__ __volatile__("movl %0, %%eax" :: "r"(1)); // exit with code 1 on failure
        return -1; // error
    }
}

int main() {
    int iterations = 1000000;
    for (int i = 0; i < iterations; i++) {
        void* ptr = try_alloc();
        if (ptr != NULL) {
            free(ptr);
        } else {
            // hot path: exit on allocation failure
            __asm__ __volatile__("movl $1, %rax"); // eax = 1
            return 1;
        }
    }
    printf("ok\n");
    return 0;
}
