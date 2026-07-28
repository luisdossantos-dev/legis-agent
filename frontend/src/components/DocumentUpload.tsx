import { useState, useRef, useCallback, type DragEvent } from "react";
import { apiClient } from "../api/client";
import { validateUploadFile } from "../api/validation";
import { t } from "../i18n";

interface DocumentUploadProps {
  onUploadComplete: () => void;
}

function DocumentUpload({ onUploadComplete }: DocumentUploadProps) {
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragCounterRef = useRef(0);

  const handleFile = async (file: File) => {
    const validation = validateUploadFile(file);
    if (!validation.valid) {
      setError(validation.error);
      return;
    }

    setError(null);
    setUploading(true);
    setProgress(0);

    try {
      await apiClient.uploadDocument(file, setProgress);
      onUploadComplete();
    } catch (err) {
      console.error("Upload failed:", err);
      setError("Error uploading file");
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  const handleDragEnter = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current += 1;
    if (dragCounterRef.current === 1) {
      setDragging(true);
    }
  }, []);

  const handleDragOver = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  }, []);

  const handleDragLeave = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current -= 1;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setDragging(false);
    }
  }, []);

  const handleDrop = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setDragging(false);

    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  }, []);

  const handleClick = () => fileInputRef.current?.click();

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      handleClick();
    }
  };

  return (
    <section aria-label={t("upload.ariaLabel")}>
      <button
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        type="button"
        aria-label={t("upload.ariaLabel")}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.docx,.txt"
          onChange={handleInputChange}
          style={{ display: "none" }}
          tabIndex={-1}
        />
        <div className="upload-icon" aria-hidden="true">
          {uploading ? "⏳" : "📄"}
        </div>
        <div className="upload-text">
          {uploading
            ? t("upload.uploading")
            : t("upload.dragDrop")}
        </div>
        <div className="upload-formats">{t("upload.formats")}</div>
      </button>
      {uploading && (
        <div style={{ marginTop: 10 }}>
          <div className="progress-bar">
            <div
              className="progress-bar-fill"
              style={{ width: `${progress}%` }}
            />
          </div>
          <div style={{ fontSize: 12, color: "var(--color-text-secondary)", textAlign: "center", marginTop: 4 }}>
            {progress}%
          </div>
        </div>
      )}
      {error && (
        <div style={{ color: "var(--color-error)", fontSize: 13, marginTop: 8 }} role="alert">
          {error}
        </div>
      )}
    </section>
  );
}

export default DocumentUpload;
