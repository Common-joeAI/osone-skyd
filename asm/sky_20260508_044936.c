#include <stdio.h>
#include <stdlib.h>
#include <time.h>

int main() {
    int sum = 0;
    for (int i = 0; i < 1000000; i++) {
        int a = rand();
        int b = rand();
        sum += ((long long)a) * b;
    }
    printf("%d\n", sum);
}

int __attribute__((noinline)) add(int x, int y) {
    register int r;
    __asm__ volatile("movl %2, %%eax\n"
                     "addl %1, %%eax\n"
                     : "=r" (r)
                     : "r" (x), "r" (y));
    return r;
}

int main() {
    for (int i = 0; i < 100000; i++) {
        int a = rand();
        int b = rand();
        add(a, b);
    }
    printf("ok\n");
    return 0;
}
