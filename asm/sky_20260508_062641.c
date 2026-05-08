#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

// Thread pool configuration
#define NUM_THREADS 4
#define MAX_WORKS 1000

// Shared variables
int works[NUM_THREADS];
unsigned long long *result;

// Hot path inline assembly
inline __asm__ volatile(
    "movq %1, %%rax\n"
    : "=r" (result[0])
    : "m" (*result)
    : "%rax"
);

void allocate(int work) {
    unsigned long long val = rand();
    result[0] = val;
}

void worker(void* arg) {
    int i;
    for (i = 0; i < MAX_WORKS; i++) {
        // Hot path
        __asm__ volatile("nop");
        if (__builtin_expect(i % NUM_THREADS == 0, 1)) {
            allocate(rand());
        }
        works[i % NUM_THREADS]++;
    }
}

int main() {
    unsigned long long start, end;
    int i;

    // Initialize shared variables
    for (i = 0; i < NUM_THREADS; i++) {
        works[i] = 0;
    }

    // Benchmark
    start = clock_t();
    pthread_t threads[NUM_THREADS];
    for (i = 0; i < NUM_THREADS; i++) {
        pthread_create(&threads[i], NULL, worker, NULL);
    }
    for (i = 0; i < NUM_THREADS; i++) {
        pthread_join(threads[i], NULL);
    }
    end = clock_t();
    printf("%llu\n", (end - start) * CLOCKS_PER_SEC / CLOCKS_PER_MS);

    // Print result
    if (works[0] == MAX_WORKS) {
        printf("ok");
    } else {
        printf("%d", works[0]);
    }
    return 0;
}
