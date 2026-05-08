#include <stdio.h>
#include <stdlib.h>
#include <sys resource.h>
#include <unistd.h>

int main() {
    int64_t cpu_usage;
    struct rusage usage;

    // Get initial CPU usage
    getrusage(RUSAGE_SELF, &usage);

    cpu_usage = usage.ru_maxrt + usage.ru_minrt - usage.ru_utime;
    if (cpu_usage == 0) cpu_usage++;

    while (1) {
        // Read current CPU usage
        getrusage(RUSAGE_SELF, &usage);
        cpu_usage = usage.ru_maxrt + usage.ru_minrt - usage.ru_utime;

        // Check for excessive CPU usage and adjust if necessary
        if (cpu_usage > 90 && cpu_usage < 100) {
            printf("Adjusting...\n");
            // Code to adjust CPU usage goes here
            printf("ok\n");
        } else if (cpu_usage >= 100) {
            printf("High CPU usage detected!\n");
            exit(1);
        }

        // Sleep for a short duration to avoid busy-waiting
        usleep(1000);
    }
}

#include <stdio.h>
#include <stdlib.h>

int main() {
    const int num_iterations = 1000000;

    clock_t start = clock();
    for (int i = 0; i < num_iterations; i++) {
        __asm__ volatile ("movl $1, %%eax"); // Hot path to prevent branch prediction
    }
    clock_t end = clock();

    double time_taken = (double)(end - start) / CLOCKS_PER_SEC;
    printf("Time taken: %.6f seconds\n");
    return 0;
}
