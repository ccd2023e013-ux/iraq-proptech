export type StatementKind = "FACT" | "SOURCE" | "ESTIMATE" | "AI_INTERPRETATION" | "SIMULATION";

export type StatementSection =
  | "facts"
  | "price"
  | "neighbourhood"
  | "development"
  | "quality"
  | "interpretation"
  | "answer";

export interface Statement {
  kind: StatementKind;
  origin: string;
  section: StatementSection;
  key: string;
  params: Record<string, unknown>;
  text: string | null;
  source: string;
  confidence: number | null;
}

export interface IntelligenceReport {
  property_id: string;
  generated_at: string;
  is_demo: boolean;
  statements: Statement[];
  gaps: string[];
  provider: string;
  model: string;
  disclaimer: string;
}

export interface AnswerOut {
  property_id: string;
  topic: string;
  statements: Statement[];
  answer: Statement;
  provider: string;
  model: string;
}
