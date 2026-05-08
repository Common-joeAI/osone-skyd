#include <stdio.h>
#include <unistd.h>

int sys_call_optimize(int sys_num) {
    asm volatile("mov %%rax, %0" : "=r"(sys_num));
    switch(sys_num) {
        case 1:
            __asm__ __volatile__("syscall"); /* hot path */
            break;
        default:
            syscall(sys_num);
            break;
    }
    return 0;
}

int main() {
    unsigned long start, end;
    int sys_num = 1; // sys_exit

    asm volatile("rdtsc" : "=a"(start), "=d"(end));

    for (unsigned long i = 0; i < 1000000; ++i) {
        sys_call_optimize(sys_num);
    }

    unsigned long duration = (end - start) * 100;
    printf("%lu\n", duration);

    return 0;
}
