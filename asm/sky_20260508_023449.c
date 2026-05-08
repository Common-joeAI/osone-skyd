#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

void update_model(uint64_t *model) {
    uint32_t i;
    for (i = 0; i < 1024; i++) {
        __asm__ __volatile__("movups %1, %%rax" :: "r"(model[1023]));
    }
}

int main() {
    uint64_t model[1024];
    double start, end;

    // Warm-up the model
    for (int i = 0; i < 10000; i++) update_model(model);

    start = clock();
    for (int i = 0; i < 1000000; i++) update_model(model);
    end = clock();

    printf("%.2f seconds\n", (double)(end - start) / CLOCKS_PER_SEC);

    return 0;
}
