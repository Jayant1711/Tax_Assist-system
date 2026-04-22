import sys
import os
import random
import time
import json
import numpy as np

# Add parent dir to path
sys.path.append(os.getcwd())

from tax_engine import TaxEngine
from nlp_engine import NLPEngine

def run_backend_benchmarks(n_cases=50000):
    print(f"--- Starting Backend Benchmark: {n_cases} cases ---")
    engine = TaxEngine()
    start_time = time.time()
    
    for i in range(n_cases):
        # Generate random profile
        data = {
            "salary": random.randint(300000, 10000000),
            "business": random.randint(0, 5000000),
            "rental": random.randint(0, 1000000),
            "80c": random.randint(0, 300000),
            "80d": random.randint(0, 100000),
            "age": random.randint(20, 85),
            "capital_gains": [
                {"type": "property_cg", "amount": random.randint(0, 100000000), "holding": "long"},
                {"type": "equity_ltcg", "amount": random.randint(0, 500000)}
            ]
        }
        res = engine.calculate_tax_advanced(data)
        
        if i % 10000 == 0:
            print(f"Processed {i} cases...")
            
    end_time = time.time()
    print(f"Benchmark Complete. Total Time: {end_time - start_time:.2f}s")
    print(f"Average speed: {(end_time - start_time)/n_cases*1000:.4f}ms per case")

def run_nlp_stress_test(n_strings=500000):
    print(f"\n--- Starting NLP Stress Test: {n_strings} strings ---")
    nlp = NLPEngine()
    session = {"state_stack": ["GATHER_TOTAL_INCOME"]}
    
    test_strings = [
        "I earn 50 lakhs in my job and 10 lakhs from my shop",
        "my salary is 25 LPA but i have 15 lakh business income",
        "i sold a plot for 2 crores which i bought 10 years ago",
        "invested 1.5L in LIC and 50k in NPS",
        "i pay 20k rent per month in Mumbai",
        "i am a farmer earning 5 lakhs from crops",
        "bought some shares last year for 5L and sold for 7L",
        "my mom is a senior citizen and i pay her health insurance"
    ]
    
    start_time = time.time()
    for i in range(n_strings):
        msg = random.choice(test_strings)
        _ = nlp.process_message(msg, session.copy())
        
        if i % 100000 == 0:
            print(f"Processed {i} strings...")
            
    end_time = time.time()
    print(f"Stress Test Complete. Total Time: {end_time - start_time:.2f}s")
    print(f"Average speed: {(end_time - start_time)/n_strings*1000:.4f}ms per extraction")

if __name__ == "__main__":
    run_backend_benchmarks(50000)
    run_nlp_stress_test(500000)
