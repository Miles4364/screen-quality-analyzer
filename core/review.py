"""人工结论独立于自动检测结果和评分。"""
REVIEW_LABELS = {'PENDING': '待复核', 'CONFIRMED': '确认异常', 'FALSE_POSITIVE': '误报'}


def review_counts(issue_count, reviews):
    counts = dict.fromkeys(REVIEW_LABELS, 0)
    records = {r['issue_ordinal']: r for r in reviews}
    for ordinal in range(issue_count):
        counts[records.get(ordinal, {}).get('status', 'PENDING')] += 1
    return counts
