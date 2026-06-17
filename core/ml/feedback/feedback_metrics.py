from typing import List, Dict, Any, Tuple

def compute_binary_metrics(y_true: List[float], y_prob: List[float]) -> Dict[str, float]:
    """
    Computes standard evaluation metrics for binary classifications:
    Accuracy, Precision, Recall, F1, ROC-AUC, Brier Score, and ECE.
    """
    n = len(y_true)
    if n == 0:
        return {
            "accuracy": 0.0,
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "roc_auc": 0.5,
            "brier_score": 0.0,
            "ece": 0.0
        }

    # Binary thresholded predictions (at 0.5)
    y_pred = [1.0 if p > 0.5 else 0.0 for p in y_prob]

    # Confusion counts
    tp = sum(1 for i in range(n) if y_true[i] == 1.0 and y_pred[i] == 1.0)
    tn = sum(1 for i in range(n) if y_true[i] == 0.0 and y_pred[i] == 0.0)
    fp = sum(1 for i in range(n) if y_true[i] == 0.0 and y_pred[i] == 1.0)
    fn = sum(1 for i in range(n) if y_true[i] == 1.0 and y_pred[i] == 0.0)

    accuracy = (tp + tn) / n
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    # Brier Score
    brier_score = sum((y_prob[i] - y_true[i]) ** 2 for i in range(n)) / n

    # ROC AUC (Mann-Whitney U statistic formulation)
    pos = [y_prob[i] for i in range(n) if y_true[i] == 1.0]
    neg = [y_prob[i] for i in range(n) if y_true[i] == 0.0]
    n_pos = len(pos)
    n_neg = len(neg)
    if n_pos == 0 or n_neg == 0:
        roc_auc = 0.5
    else:
        score = 0.0
        for p in pos:
            for q in neg:
                if p > q:
                    score += 1.0
                elif p == q:
                    score += 0.5
        roc_auc = score / (n_pos * n_neg)

    # Expected Calibration Error (ECE) with 10 bins
    n_bins = 10
    ece = 0.0
    for i in range(n_bins):
        bin_lower = i / n_bins
        bin_upper = (i + 1) / n_bins
        
        # Bin inclusion indices
        bin_indices = [idx for idx in range(n) if bin_lower <= y_prob[idx] < bin_upper]
        if i == n_bins - 1:
            bin_indices += [idx for idx in range(n) if y_prob[idx] == bin_upper]
        bin_indices = list(set(bin_indices))
        
        bin_size = len(bin_indices)
        if bin_size > 0:
            bin_true = [y_true[idx] for idx in bin_indices]
            bin_p = [y_prob[idx] for idx in bin_indices]
            
            bin_acc = sum(bin_true) / bin_size
            bin_conf = sum(bin_p) / bin_size
            
            ece += (bin_size / n) * abs(bin_acc - bin_conf)

    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "roc_auc": roc_auc,
        "brier_score": brier_score,
        "ece": ece
    }

def compute_multiclass_metrics(y_true: List[str], y_pred: List[str]) -> Dict[str, Any]:
    """
    Computes evaluation metrics for multiclass predictions:
    Accuracy, Macro-F1, and Confusion Matrix.
    """
    n = len(y_true)
    if n == 0:
        return {
            "accuracy": 0.0,
            "macro_f1": 0.0,
            "confusion_matrix": {"classes": [], "matrix": {}}
        }

    accuracy = sum(1 for i in range(n) if y_true[i] == y_pred[i]) / n

    # Macro F1
    classes = sorted(list(set(y_true + y_pred)))
    f1_scores = []
    for c in classes:
        # One-vs-rest binary metrics
        c_true = [1.0 if y == c else 0.0 for y in y_true]
        c_pred = [1.0 if y == c else 0.0 for y in y_pred]
        
        tp = sum(1 for i in range(n) if c_true[i] == 1.0 and c_pred[i] == 1.0)
        fp = sum(1 for i in range(n) if c_true[i] == 0.0 and c_pred[i] == 1.0)
        fn = sum(1 for i in range(n) if c_true[i] == 1.0 and c_pred[i] == 0.0)
        
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
        f1_scores.append(f1)
        
    macro_f1 = sum(f1_scores) / len(classes) if classes else 0.0

    # Confusion Matrix
    matrix = {}
    for actual in classes:
        matrix[actual] = {}
        for predicted in classes:
            count = sum(1 for i in range(n) if y_true[i] == actual and y_pred[i] == predicted)
            matrix[actual][predicted] = count

    return {
        "accuracy": accuracy,
        "macro_f1": macro_f1,
        "confusion_matrix": {"classes": classes, "matrix": matrix}
    }
