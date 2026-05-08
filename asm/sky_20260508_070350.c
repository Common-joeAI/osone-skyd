#include <stdio.h>

void update_cpu_monitor(float utilization) {
    float low_utilization_threshold = 0.2;
    
    __asm__ volatile (
        "movl %0, %%cx\n"
        : "=m" (utilization)
        : 
        : "%cx"
    );
    
    if (utilization <= low_utilization_threshold) {
        printf("ok\n");
        return;
    }
}

int main() {
    float utilization = 0.1; // 10%
    for (int i = 0; i < 1000000; i++) {
        update_cpu_monitor(utilization);
    }
    
    printf("%.2f%% average utilization\n", utilization);
    return 0;
}
