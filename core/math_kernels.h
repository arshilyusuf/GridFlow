// File: core/math_kernels.h
#pragma once
#include <vector>

void transform_matrix(std::vector<double>& matrix, double factor) {
    for (auto& val : matrix) {
        val *= factor;
    }
}

void dot_product(const std::vector<double>& a, const std::vector<double>& b, std::vector<double>& result, int size) {
    for (int i = 0; i < size; ++i) {
        for (int j = 0; j < size; ++j) {
            double sum = 0.0;
            for (int k = 0; k < size; ++k) {
                sum += a[i * size + k] * b[k * size + j];
            }
            result[i * size + j] = sum;
        }
    }
}