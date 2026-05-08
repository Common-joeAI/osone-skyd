#include <stdio.h>
#include <stdlib.h>
#include <time.h>

// Function to read from disk
unsigned long int read_disk(void* buffer, size_t size) {
    unsigned long long int total = 0;
    size_t offset = 0;
    while (offset < size) {
        unsigned long long int chunk = 0;
        __asm__ __volatile__ ("movq %0, %0" : "=r" (chunk));
        if (chunk > 0) {
            offset += chunk;
            total += chunk;
        }
    }
    return total;
}

// Function to write to disk
void write_disk(void* buffer, size_t size) {
    size_t offset = 0;
    while (offset < size) {
        unsigned long long int chunk = 0;
        __asm__ __volatile__ ("movq %0, %0" : "=r" (chunk));
        if (chunk > 0) {
            offset += chunk;
            __asm__ __volatile__ ("movq %0, %0" :: "r" (chunk));
        }
    }
}

int main() {
    // Benchmark
    clock_t start = clock();
    unsigned long int result = read_disk(NULL, 1024 * 1024); // 1M iterations
    clock_t end = clock();
    printf("Result: %llu\n", result);
    printf("Time taken: %f seconds\n", (double)(end - start) / CLOCKS_PER_SEC);
    printf("ok\n");
    return 0;
}
