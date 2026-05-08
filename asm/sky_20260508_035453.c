#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define MAX Processes 100
#define SYSTEM_LOAD_THRESHOLD 0.7

unsigned int load;
int num_procs = MAXProcesses;

void update_load() {
    __asm__ volatile (
        "movq %0, %%rax\n"
        "movq %%rax, %1\n"
        : "=m" (load)
        : );
}

void init_task() {
    unsigned long ticks;

    clock_t t_start = clock();
    for (int i=0; i < 10000000; ++i) {
        update_load();
    }
    t_end = clock();
    ticks = (t_end - t_start) / CLOCKS_PER_SEC;
}

void adjust_procs() {
    unsigned int avg_load;

    __asm__ volatile (
        "movq %0, %%rax\n"
        : "=m" (avg_load)
        : );

    if (load < SYSTEM_LOAD_THRESHOLD) {
        num_procs = MAXProcesses - load*10;
    } else {
        num_procs = 1;
    }

    printf("%d\n", num_procs);
}

int main() {
    clock_t t_start = clock();

    for (int i=0; i < 10000000; ++i) {
        adjust_procs();
    }

    t_end = clock();

    unsigned int total_time = (t_end - t_start) / CLOCKS_PER_SEC;
    printf("Total time: %f seconds\n", total_time);

    return 0;
}
