#include <stdio.h>
#include <stdlib.h>

int ollama allocation(int size) {
    int *ptr = malloc(size);
    __asm__ __volatile__("movq %0, %rax" :: "r"(ptr));
    return ptr;
}

int main() {
    int i;
    for (i = 0; i < 1000000; i++)
        ollama(16);

    printf("%d\n", i);
    free(NULL);
    return 0;
}
