#include <stdio.h>
#include <stdlib.h>
#include <pthread.h>

// Structure to hold allocated resources
typedef struct {
    int* ptr;
    size_t len;
} AllocRes;

// Thread function to allocate resource
static void* alloc_thread(void* arg) {
    AllocRes* res = (AllocRes*)arg;
    res->ptr = (int*)malloc(res->len);
    return NULL;
}

// Main function
int main() {
    int num_allocs = 1000000;
    pthread_t threads[num_allocs];
    AllocRes* res;

    // Create and start the thread pool
    for (int i = 0; i < num_allocs; i++) {
        res = malloc(sizeof(AllocRes));
        res->len = 10;
        res->ptr = NULL;

        pthread_create(&threads[i], NULL, alloc_thread, res);
    }

    // Wait for all threads to finish
    for (int i = 0; i < num_allocs; i++) {
        pthread_join(threads[i], NULL);
    }

    // Print result
    printf("%d\n", 1);

    return 0;
}
