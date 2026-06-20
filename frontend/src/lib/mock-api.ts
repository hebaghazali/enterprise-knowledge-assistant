// Mock API for the Enterprise Knowledge Assistant.
// Replace these functions with real FastAPI calls later.

export type DocStatus = "Uploaded" | "Chunked" | "Vector Indexed";

export interface Document {
  id: string;
  name: string;
  type: "PDF" | "TXT" | "MD";
  status: DocStatus;
  chunks: number;
  createdAt: string;
}

export interface RetrievedChunk {
  id: string;
  document: string;
  score: number;
  preview: string;
}

export interface AnswerResponse {
  answer: string;
  groundedness: number; // 0..1
  sources: { document: string; page?: number; snippet: string }[];
  chunks: RetrievedChunk[];
  latencyMs: number;
}

export const mockMetrics = {
  documents: 128,
  chunks: 14_823,
  questions: 2_417,
  avgRetrievalMs: 184,
};

export const mockDocuments: Document[] = [
  { id: "1", name: "Employee Handbook 2025.pdf", type: "PDF", status: "Vector Indexed", chunks: 312, createdAt: "2025-04-12" },
  { id: "2", name: "Q1 Financial Report.pdf", type: "PDF", status: "Vector Indexed", chunks: 184, createdAt: "2025-04-22" },
  { id: "3", name: "Engineering Onboarding.md", type: "MD", status: "Chunked", chunks: 67, createdAt: "2025-05-01" },
  { id: "4", name: "Security Policy.txt", type: "TXT", status: "Vector Indexed", chunks: 41, createdAt: "2025-05-08" },
  { id: "5", name: "Product Roadmap H2.pdf", type: "PDF", status: "Uploaded", chunks: 0, createdAt: "2025-06-02" },
  { id: "6", name: "API Architecture.md", type: "MD", status: "Vector Indexed", chunks: 96, createdAt: "2025-06-10" },
];

export async function fetchMetrics() {
  await delay(120);
  return mockMetrics;
}

export async function fetchDocuments(): Promise<Document[]> {
  await delay(150);
  return mockDocuments;
}

export async function uploadDocument(file: { name: string; type: Document["type"] }): Promise<Document> {
  await delay(400);
  return {
    id: crypto.randomUUID(),
    name: file.name,
    type: file.type,
    status: "Uploaded",
    chunks: 0,
    createdAt: new Date().toISOString().slice(0, 10),
  };
}

export async function askQuestion(question: string): Promise<AnswerResponse> {
  await delay(700);
  return {
    answer:
      `Based on the indexed knowledge base, ${question.trim().replace(/\?$/, "")} is addressed across multiple internal policies. ` +
      "Employees are entitled to 25 paid vacation days annually, with carry-over capped at 5 days. " +
      "Requests must be submitted via the HR portal at least two weeks in advance and approved by a direct manager.",
    groundedness: 0.92,
    sources: [
      { document: "Employee Handbook 2025.pdf", page: 42, snippet: "All full-time employees receive 25 days of paid vacation per calendar year…" },
      { document: "Security Policy.txt", snippet: "Time-off requests must be logged in the HR system and reviewed by the reporting manager…" },
    ],
    chunks: [
      { id: "c1", document: "Employee Handbook 2025.pdf", score: 0.91, preview: "Section 4.2 — Paid Time Off. All full-time employees receive 25 days of paid vacation…" },
      { id: "c2", document: "Employee Handbook 2025.pdf", score: 0.87, preview: "Carry-over rules: Up to 5 unused vacation days may be carried into the following year…" },
      { id: "c3", document: "Security Policy.txt", score: 0.74, preview: "Time-off requests submitted via the HR portal are routed to the employee's direct manager…" },
      { id: "c4", document: "Engineering Onboarding.md", score: 0.61, preview: "New hires should coordinate vacation during their first 90 days with their team lead…" },
    ],
    latencyMs: 182,
  };
}

function delay(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

// ---------- Document details (mock) ----------

export interface DocChunk {
  index: number;
  chars: number;
  tokens: number;
  text: string;
}

export interface RetrievalHit {
  chunkIndex: number;
  score: number;
  text: string;
  highlight: string;
}

export interface DocumentDetails {
  summary: string;
  extractedText: string[];
  chunks: DocChunk[];
  vectorIndex: {
    model: string;
    collection: string;
    indexed: boolean;
    indexedAt: string;
    vectorCount: number;
    dimensions: number;
  };
  retrieval: {
    question: string;
    hits: RetrievalHit[];
  };
}

const detailLibrary: Record<string, Partial<DocumentDetails>> = {
  "Employee Handbook 2025.pdf": {
    summary:
      "This handbook covers employee onboarding, remote work policies, benefits, security guidelines, and performance review processes for all full-time staff.",
    extractedText: [
      "Welcome to Acme Corporation. This handbook outlines the policies, expectations, and benefits that apply to every full-time employee. It is reviewed annually by People Operations and the Office of the General Counsel.",
      "Remote Work Policy. Employees are eligible for up to three remote work days per week, subject to manager approval. Core collaboration hours are 10:00–15:00 in the employee's local timezone. Cross-functional team meetings should be scheduled within this window.",
      "Paid Time Off. All full-time employees receive 25 days of paid vacation per calendar year. Up to 5 unused days may be carried into the following year. Requests must be submitted via the HR portal at least two weeks in advance and approved by the reporting manager.",
      "Performance Reviews. Formal reviews are conducted twice per year, in Q2 and Q4. Reviews include a self-assessment, peer feedback from three colleagues, and a structured 1:1 with the direct manager. Compensation adjustments follow the Q4 cycle.",
      "Security & Confidentiality. All employees must complete annual security training and use company-managed devices for any access to production systems. Sharing credentials, even within a team, is strictly prohibited.",
    ],
    retrieval: {
      question: "How many remote work days are employees allowed per week?",
      hits: [
        { chunkIndex: 2, score: 0.94, text: "Remote Work Policy. Employees are eligible for up to three remote work days per week, subject to manager approval. Core collaboration hours are 10:00–15:00 in the employee's local timezone.", highlight: "up to three remote work days per week" },
        { chunkIndex: 7, score: 0.81, text: "Hybrid teams should coordinate in-office days at least one week in advance. Managers may require additional on-site presence during quarterly planning weeks.", highlight: "in-office days" },
        { chunkIndex: 12, score: 0.68, text: "Equipment stipends are available for employees working remotely more than two days per week, covering monitors, ergonomic chairs, and high-speed internet.", highlight: "remotely more than two days per week" },
      ],
    },
  },
  "Security Policy.txt": {
    summary:
      "Defines access control, credential management, incident response, and data handling requirements across all production and corporate systems.",
    extractedText: [
      "Purpose. This policy establishes the minimum security controls required to protect company and customer data across all environments classified as Internal, Confidential, or Restricted.",
      "Access Control. Access to production systems is granted through SSO with hardware-backed multi-factor authentication. All privileged access is time-bound and audited via the access-review pipeline.",
      "Incident Response. Suspected incidents must be reported to security@acme.com within 30 minutes of discovery. The on-call security engineer will triage and, if confirmed, open a Sev1 incident channel.",
      "Data Handling. Customer data may only be processed within approved regions. Exports require a signed DPA and an approved data-handling justification recorded in the GRC system.",
    ],
    retrieval: {
      question: "What is the incident response window for suspected breaches?",
      hits: [
        { chunkIndex: 3, score: 0.92, text: "Incident Response. Suspected incidents must be reported to security@acme.com within 30 minutes of discovery.", highlight: "within 30 minutes of discovery" },
        { chunkIndex: 5, score: 0.76, text: "Sev1 incidents trigger an automated page to the on-call security engineer and a parallel notification to the CISO.", highlight: "on-call security engineer" },
      ],
    },
  },
};

const defaultDetails = (doc: Document): DocumentDetails => ({
  summary: `This document contains structured enterprise content related to ${doc.name.replace(/\.[^.]+$/, "")}. It has been processed by the ingestion pipeline and is available for retrieval.`,
  extractedText: [
    `Executive Summary. ${doc.name.replace(/\.[^.]+$/, "")} consolidates internal knowledge across multiple business units, with cross-references to related policies and operational runbooks.`,
    "Scope. The content applies to all employees, contractors, and partners who interact with the systems and processes described herein, unless explicitly noted otherwise.",
    "Definitions. Key terminology is standardized across the corporate knowledge base. Where conflicts exist, the most recent published version of this document takes precedence.",
    "Governance. This document is reviewed quarterly. Change requests should be submitted through the internal knowledge portal and reviewed by the document owner.",
  ],
  chunks: [],
  vectorIndex: {
    model: "sentence-transformers/all-MiniLM-L6-v2",
    collection: "enterprise_knowledge_chunks",
    indexed: doc.status === "Vector Indexed",
    indexedAt: doc.createdAt,
    vectorCount: doc.chunks,
    dimensions: 384,
  },
  retrieval: {
    question: "What does this document cover and who is it for?",
    hits: [
      { chunkIndex: 1, score: 0.88, text: `Scope. The content applies to all employees, contractors, and partners who interact with the systems described in ${doc.name}.`, highlight: "all employees, contractors, and partners" },
      { chunkIndex: 3, score: 0.72, text: "Governance. This document is reviewed quarterly. Change requests should be submitted through the internal knowledge portal.", highlight: "reviewed quarterly" },
    ],
  },
});

export function getDocumentDetails(doc: Document): DocumentDetails {
  const base = defaultDetails(doc);
  const override = detailLibrary[doc.name] ?? {};
  const merged: DocumentDetails = {
    ...base,
    ...override,
    vectorIndex: { ...base.vectorIndex, ...(override.vectorIndex ?? {}) },
    retrieval: override.retrieval ?? base.retrieval,
    extractedText: override.extractedText ?? base.extractedText,
  };

  // Generate chunk list from extracted paragraphs (plus a few extras)
  const paragraphs = merged.extractedText;
  const totalChunks = Math.max(doc.chunks, paragraphs.length);
  const chunks: DocChunk[] = Array.from({ length: Math.min(totalChunks, 24) }, (_, i) => {
    const text = paragraphs[i % paragraphs.length];
    return {
      index: i + 1,
      chars: text.length,
      tokens: Math.round(text.length / 4),
      text,
    };
  });
  merged.chunks = chunks;
  merged.vectorIndex.vectorCount = doc.chunks || chunks.length;
  return merged;
}