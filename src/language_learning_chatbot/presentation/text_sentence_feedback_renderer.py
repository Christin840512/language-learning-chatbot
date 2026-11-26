"""Render sentence feedback for a local plain-text client."""

from ..application import SentenceFeedback, SentenceFeedbackKind


def render_sentence_feedback(feedback: SentenceFeedback) -> str:
    """Turn validated application feedback into user-facing text."""

    if feedback.kind is SentenceFeedbackKind.ALREADY_NATURAL:
        return "Well done!"

    if feedback.sentence is None or feedback.explanation is None:
        raise ValueError("feedback must be validated before rendering")

    if feedback.kind is SentenceFeedbackKind.CORRECTION:
        return f"{feedback.sentence}\n\n{feedback.explanation}"

    if feedback.kind is SentenceFeedbackKind.SUGGESTION:
        if feedback.original_validity_note is None:
            raise ValueError("suggestion must include an original validity note")
        return (
            f"{feedback.original_validity_note}\n\n"
            f"{feedback.sentence}\n\n"
            f"{feedback.explanation}"
        )

    raise ValueError(f"Unsupported sentence feedback kind: {feedback.kind!r}")

