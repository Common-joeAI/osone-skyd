#include <stdio.h>
#include <stdlib.h>

// Constants
#define SYSTEM_LOAD_THRESHOLD 80
#define ALERT_INTERVAL_MS 1000

int main() {
    // Initialize system load average
    long sys_load_avg = 0;

    while (1) {
        // Read current system load average
        __asm__ volatile("rdtsc" : "=A"(sys_load_avg));

        // Check if threshold is exceeded
        if (sys_load_avg > SYSTEM_LOAD_THRESHOLD * 100) {
            printf("ALERT\n");
        }

        // Sleep for interval
        __asm__ volatile("sleep $%d" : : "r" (ALERT_INTERVAL_MS));
    }

    return 0;
}

int main() {
    long start = clock();
    for (int i = 0; i < 1000000; ++i);
    printf("%f\n", (float)(clock() - start) / CLOCKS_PER_SEC);

    return 0;
}
