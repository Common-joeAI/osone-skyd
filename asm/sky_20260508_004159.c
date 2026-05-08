#include <stdio.h>
#include <string.h>

// Kernel module patcher
void patch_kernel_module(void) {
    unsigned long address = 0x12345678; // replace with actual address
    unsigned char* data = "example_data";
    int length = strlen(data);

    // Calculate checksum using a simple XOR sum
    unsigned long checksum = 0;
    for (int i = 0; i < length; i++) {
        __asm__ __volatile__("xorl %0, %0" : "=r"(checksum));
        __asm__ __volatile__("xorb %1, %0" : "+r"(data[i]), "r"(checksum));
    }

    // Print the checksum
    printf("%lu\n", checksum);

    // Write data to kernel module
    unsigned long offset = 16; // replace with actual offset
    for (int i = 0; i < length; i++) {
        __asm__ __volatile__("movl %4, %0" :: "r"(data[i]), "r"(offset));
        __asm__ __volatile__("addl $8, %1" : "=r"(offset), "+r"(offset));
    }

    // Print success message
    printf("ok\n");
}

int main() {
    unsigned long start = clock();
    for (int i = 0; i < 1000000; i++) patch_kernel_module();
    unsigned long end = clock();

    double time_taken = (end - start) / CLOCKS_PER_SEC;
    printf("%.6f sec\n", time_taken);

    return 0;
}
