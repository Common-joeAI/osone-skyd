#include <stdio.h>
#include <stdlib.h>

void print_result(void) {
    #ifdef __GNUC__
        printf("%d\n", result);
    #else
        printf("%d\n", result);
    #endif
}

__inline __attribute__((always_inline)) void hot_path(int a, int b) {
    __asm__ volatile("movq %0, %%rax\n"
                     "imull %%rax, %%rax\n"
                     : "=r" (result), "a" (b)
                     : "a" (a));
}

int main() {
    int result = 0;
    for (int i = 0; i < 1000000; i++) {
        hot_path(1, 2);
        __asm__ volatile("addq $10, %%rax\n"
                         "movq %%rax, %0\n"
                         : "=m" (result));
    }
    print_result();

    int slow_result = 0;
    for (int i = 0; i < 1000000; i++) {
        result = 1 * 2 + 10;
    }
    printf("%d\n", slow_result);

    return 0;
}
