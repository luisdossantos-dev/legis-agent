/**
 * Client-side validation utilities.
 *
 * All validation runs BEFORE sending data to the server,
 * giving the user immediate feedback on invalid inputs.
 */

// ── Constants (must match backend config) ───────────────────

export const MAX_UPLOAD_SIZE = 50 * 1024 * 1024; // 50 MB
export const MAX_FILENAME_LENGTH = 255;
export const SUPPORTED_EXTENSIONS = [".pdf", ".docx", ".txt"] as const;
export const MAX_CLAUSE_TEXT_LENGTH = 10000;
export const MAX_FIELD_LENGTH = 1000;
export const MAX_CUSTOM_QUERY_LENGTH = 2000;

// ── File upload validation ──────────────────────────────────

export interface FileValidationResult {
  valid: boolean;
  error: string | null;
}

export function validateUploadFile(file: File): FileValidationResult {
  // Check file exists
  if (!file || file.size === 0) {
    return { valid: false, error: "File is empty." };
  }

  // Check filename length
  if (file.name.length > MAX_FILENAME_LENGTH) {
    return {
      valid: false,
      error: `Filename is too long (${file.name.length} chars). Maximum is ${MAX_FILENAME_LENGTH}.`,
    };
  }

  // Check extension
  const ext = "." + file.name.split(".").pop()?.toLowerCase();
  if (!ext || !(SUPPORTED_EXTENSIONS as readonly string[]).includes(ext)) {
    return {
      valid: false,
      error: `Unsupported format "${ext}". Supported formats: PDF, DOCX, TXT.`,
    };
  }

  // Check file size
  if (file.size > MAX_UPLOAD_SIZE) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    const maxMb = MAX_UPLOAD_SIZE / (1024 * 1024);
    return {
      valid: false,
      error: `File too large (${sizeMb} MB). Maximum allowed size is ${maxMb} MB.`,
    };
  }

  return { valid: true, error: null };
}

// ── Email draft validation ──────────────────────────────────

export interface EmailDraftValidation {
  valid: boolean;
  errors: Record<string, string>;
}

export function validateEmailDraft(
  actType: string,
  fields: Record<string, string>,
  requiredFields: string[],
): EmailDraftValidation {
  const errors: Record<string, string> = {};

  if (!actType) {
    errors.act_type = "Act type is required.";
  }

  // Check each required field
  for (const field of requiredFields) {
    const value = (fields[field] || "").trim();
    if (!value) {
      errors[field] = `${field.replace(/_/g, " ")} is required.`;
    } else if (value.length > MAX_FIELD_LENGTH) {
      errors[field] = `${field.replace(/_/g, " ")} is too long (max ${MAX_FIELD_LENGTH} chars).`;
    }
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

// ── Clause review validation ─────────────────────────────────

export interface ClauseReviewValidation {
  valid: boolean;
  errors: Record<string, string>;
}

export function validateClauseReview(
  clauseText: string,
): ClauseReviewValidation {
  const errors: Record<string, string> = {};

  if (!clauseText || !clauseText.trim()) {
    errors.clause_text = "Clause text is required.";
  } else if (clauseText.length > MAX_CLAUSE_TEXT_LENGTH) {
    errors.clause_text = `Clause text is too long (${clauseText.length} chars). Maximum is ${MAX_CLAUSE_TEXT_LENGTH}.`;
  }

  return {
    valid: Object.keys(errors).length === 0,
    errors,
  };
}

// ── Generic helpers ─────────────────────────────────────────

export function isValidUUID(value: string): boolean {
  return /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(
    value,
  );
}

export function isNonEmpty(value: string | null | undefined): boolean {
  return typeof value === "string" && value.trim().length > 0;
}
