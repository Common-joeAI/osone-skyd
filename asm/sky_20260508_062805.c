#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define NUM_THREADS 4
#define NUM_ITERATIONS 1000000

void* thread_func(void* arg) {
    __asm__ volatile (
        "mov %%rdi, %0\n"
        : "=r" (num_threads)
        : "r" (arg)
        : "cc", "memory"
    );
    return NULL;
}

int main() {
    clock_t start, end;
    int num_threads = NUM_THREADS;

    srand(time(NULL));
    for (int i = 0; i < 10; i++) {
        start = clock();
        thread_pool(num_threads);
        end = clock();

        double time_taken = (double)(end - start) / CLOCKS_PER_SEC;
        printf("Time taken to run pool: %f\n", time_taken);

        num_threads *= 2;
    }

    return 0;
}

void thread_pool(int num_threads) {
    int threads[num_threads];
    for (int i = 0; i < num_threads; i++) {
        threads[i] = rand() % 100000;
    }
}

void* hot_thread_func(void* arg) {
    __asm__ volatile (
        "mov %%rdi, %0\n"
        : "=r" (num_threads)
        : "r" (arg)
        : "cc", "memory"
    );
    return NULL;
}
