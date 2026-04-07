"""
Lead-Ops · Score Reporting Utility
==================================
Produces a human-readable performance breakdown of a final Reward.
"""

from typing import Any
from models import Reward

def generate_score_report(reward: Reward) -> str:
    """
    Takes a completed episode Reward object and formats a report.
    """
    
    header = f"=== Episode Score Report ==="
    task_info = f"Task: {reward.task_id.value.upper()}\n"
    total_info = f"Final Score: {reward.total:.2f}/1.00\n"
    
    if "[SUCCESS]" in reward.message:
        success_line = "Evaluation: ✅ SUCCESS\n"
    else:
        success_line = f"Evaluation: {'✅ SUCCESS' if reward.total >= 0.8 else '❌ FAILED'}\n"
    
    report = [header, task_info, total_info, success_line, "-" * 30]
    report.append("Component Breakdown:")
    
    # Sort components: positive first, then negative penalties
    positives = [c for c in reward.components if c.value > 0]
    negatives = [c for c in reward.components if c.value < 0]
    zeros = [c for c in reward.components if c.value == 0]
    
    for c in positives:
        report.append(f"  [+] {c.name}: +{c.value:.2f} (Weight: {c.weight})")
        if c.reason:
            report.append(f"      Ans: {c.reason}")
            
    for c in zeros:
        report.append(f"  [~] {c.name}:  0.00 (Weight: {c.weight})")
        if c.reason:
            report.append(f"      Ans: {c.reason}")
            
    for c in negatives:
        report.append(f"  [-] {c.name}: {c.value:.2f}")
        if c.reason:
            report.append(f"      Penalty: {c.reason}")
    
    report.append("-" * 30)
    report.append(f"Summary: {reward.message.replace(' [SUCCESS]', '')}")
    return "\n".join(report)

def print_score_report(reward: Reward) -> None:
    print("\n" + generate_score_report(reward) + "\n")
