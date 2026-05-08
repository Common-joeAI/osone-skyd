#include <stdio.h>
#include <stdlib.h>
#include <sys/time.h>

#define NUM_THREADS 4

int update_scheduler(int** threads) {
    int total_weight = 0;
    for (int i = 0; i < NUM_THREADS; i++) {
        struct timeval start, end;
        gettimeofday(&start, NULL);

        // Hot path
        __asm__ volatile (
            "movq %0, %%rax\n"
            "movq %1, %%rbx\n"
            "mulq $5\n"
            : "=r" (total_weight)
            : "r" (*threads[i]), "r" (NUM_THREADS), "r" (start)
        );

        gettimeofday(&end, NULL);
        int wait_time = (end.tv_sec - start.tv_sec) * 1000000 + (end.tv_usec - start.tv_usec);

        if (wait_time < 10) {
            // Cold path
            for (int j = 0; j < wait_time; j++) {
                total_weight += (*threads[i]) * NUM_THREADS;
            }
        } else {
            total_weight += (*threads[i]);
        }
    }

    return total_weight;
}

void benchmark() {
    int** threads = malloc(NUM_THREADS * sizeof(int*));
    for (int i = 0; i < NUM_THREADS; i++) {
        threads[i] = malloc(sizeof(int));
        *threads[i] = rand() % 100;
    }

    int result = update_scheduler(threads);
    free(threads);

    printf("%d\n", result);
}

int main() {
    srand(time(NULL));
    benchmark();
    return 0;
}
