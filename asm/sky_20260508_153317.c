#include <stdio.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>

#define SECTOR_SIZE 4096
#define NUM_ITERATIONS 1000000

unsigned long long perform_read(void) {
    unsigned char buffer[SECTOR_SIZE];
    __asm__ __volatile__("movl %0, %eax" :: "r"(buffer) : : "rax");
    return (unsigned long long)buffer[0];
}

unsigned long long perform_write(void) {
    unsigned char buffer[SECTOR_SIZE];
    for (int i = 0; i < SECTOR_SIZE; i++) {
        buffer[i] = i;
    }
    __asm__ __volatile__("movl %0, %eax" :: "r"(buffer) : : "rax");
    return (unsigned long long)buffer[0];
}

int main() {
    unsigned long long total_read = 0;
    unsigned long long total_write = 0;

    struct timespec start, end;

    clock_gettime(CLOCK_REALTIME, &start);

    for (int i = 0; i < NUM_ITERATIONS; i++) {
        total_read += perform_read();
        total_write += perform_write();
    }

    clock_gettime(CLOCK_REALTIME, &end);
    unsigned long long duration = (end.tv_sec - start.tv_sec) * 1000000000 + (end.tv_nsec - start.tv_nsec);
    printf("%llu\n", total_read + total_write);
    printf("Time taken: %llu ns\n", duration);
    return 0;
}
