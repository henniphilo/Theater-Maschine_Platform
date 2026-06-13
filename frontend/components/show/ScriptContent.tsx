import { splitSentences } from "@/lib/text/splitSentences";

export function ScriptContent({
  text,
  activeSentenceIndex
}: {
  text: string;
  activeSentenceIndex?: number;
}) {
  const sentences = splitSentences(text);

  if (activeSentenceIndex === undefined || sentences.length <= 1) {
    return <div className="bubbleContent">{text}</div>;
  }

  return (
    <div className="bubbleContent scriptContent" aria-live="polite">
      {sentences.map((sentence, index) => {
        let className = "scriptSentence scriptPending";
        if (index < activeSentenceIndex) className = "scriptSentence scriptSpoken";
        else if (index === activeSentenceIndex) className = "scriptSentence scriptCurrent";

        return (
          <span key={`${index}-${sentence.slice(0, 12)}`} className={className}>
            {sentence}
            {index < sentences.length - 1 ? " " : ""}
          </span>
        );
      })}
    </div>
  );
}
