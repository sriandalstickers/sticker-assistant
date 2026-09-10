import React, { useState } from 'react';
import './styles.css';

const API_BASE = "http://127.0.0.1:8000/api";

export default function App() {
  const [file, setFile] = useState<File | null>(null);
  const [projectId, setProjectId] = useState<number | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string>("");
  const [checkerReport, setCheckerReport] = useState<any>(null);
  const [traceResult, setTraceResult] = useState<any>(null);
  const [cdrGuide, setCdrGuide] = useState<any>(null);
  const [customText, setCustomText] = useState<string>("GAMING");
  const [fontSize, setFontSize] = useState<number>(48);
  const [widthMm, setWidthMm] = useState<number>(100);
  const [heightMm, setHeightMm] = useState<number>(100);
  const [loading, setLoading] = useState<boolean>(false);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    const formData = new FormData();
    formData.append("file", file);

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/upload`, {
        method: "POST",
        body: formData,
      });
      const data = await response.json();
      if (response.ok) {
        setProjectId(data.project_id);
        setUploadStatus("Artwork uploaded successfully. Original preserved!");
      } else {
        setUploadStatus(`Error: ${data.detail}`);
      }
    } catch (err) {
      setUploadStatus("Failed to connect to backend server.");
    }
    setLoading(false);
  };

  const handleMakeCutReady = async () => {
    if (!projectId) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/make-cut-ready`, {
        method: "POST",
      });
      const data = await response.json();
      if (response.ok) {
        setCheckerReport(data.report);
      } else {
        alert(`Error: ${data.detail}`);
      }
    } catch (err) {
      alert("Failed to execute Cut Ready pipeline.");
    }
    setLoading(false);
  };

  const handleTraceVector = async () => {
    if (!projectId) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/trace`, {
        method: "POST",
      });
      const data = await response.json();
      if (response.ok) {
        setTraceResult(data);
      } else {
        alert(`Error: ${data.detail}`);
      }
    } catch (err) {
      alert("Failed to trace raster into vector. Note: CDR files require a PNG/JPEG preview export for tracing.");
    }
    setLoading(false);
  };

  const handleAddTextVector = async () => {
    if (!projectId) return;

    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/add-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: customText, font_size: fontSize }),
      });
      const data = await response.json();
      if (response.ok) {
        setTraceResult(data);
      } else {
        alert(`Error: ${data.detail}`);
      }
    } catch (err) {
      alert("Failed to generate vector text.");
    }
    setLoading(false);
  };

  const handleCdrWorkflow = async () => {
    if (!projectId) return;

    try {
      const response = await fetch(`${API_BASE}/projects/${projectId}/export/cdr-guide`);
      const data = await response.json();
      if (response.ok) {
        setCdrGuide(data);
      } else {
        alert(`Error: ${data.detail}`);
      }
    } catch (err) {
      alert("Failed to fetch CorelDRAW workflow guide.");
    }
  };

  return (
    <div className="container">
      <header className="header">
        <h1>Sticker & Vinyl Cutting Assistant</h1>
        <p>Private Production Workshop for CorelDRAW & Vinyl Plotters</p>
      </header>

      <div className="workspace">
        {/* Left Panel: Controls & Upload */}
        <div className="panel control-panel">
          <h2>1. Upload Artwork</h2>
          <form onSubmit={handleUpload}>
            <input type="file" onChange={handleFileChange} accept=".pdf,.cdr,.jpg,.jpeg,.png" />
            <button type="submit" disabled={!file || loading} className="btn-secondary">
              {loading ? "Processing..." : "Upload & Lock Original"}
            </button>
          </form>
          {uploadStatus && <p className="status-msg">{uploadStatus}</p>}

          {projectId && (
            <>
              <hr />
              <h2>2. Physical Dimensions</h2>
              <div className="dimension-inputs">
                <label>
                  Width (mm):
                  <input type="number" value={widthMm} onChange={(e) => setWidthMm(Number(e.target.value))} />
                </label>
                <label>
                  Height (mm):
                  <input type="number" value={heightMm} onChange={(e) => setHeightMm(Number(e.target.value))} />
                </label>
              </div>

              <hr />
              <h2>3. Production Engine</h2>
              <button onClick={handleMakeCutReady} className="btn-primary-cut">
                🚀 MAKE CUT READY
              </button>

              <button onClick={handleTraceVector} className="btn-secondary" style={{ marginTop: '10px' }}>
                ✏️ Trace Raster to Clean Vector (SVG)
              </button>

              <div style={{ marginTop: '15px', background: '#222', padding: '10px', borderRadius: '4px' }}>
                <h3 style={{ fontSize: '0.95rem', marginBottom: '8px', color: '#ff9800' }}>Custom Text Vector Generator</h3>
                <input 
                  type="text" 
                  value={customText} 
                  onChange={(e) => setCustomText(e.target.value)} 
                  placeholder="Enter text (e.g. GAMING)"
                  style={{ width: '100%', padding: '6px', marginBottom: '8px', background: '#111', color: '#fff', border: '1px solid #444', borderRadius: '4px' }}
                />
                <label style={{ fontSize: '0.85rem', color: '#ccc', display: 'block', marginBottom: '6px' }}>
                  Font Size (px): 
                  <input 
                    type="number" 
                    value={fontSize} 
                    onChange={(e) => setFontSize(Number(e.target.value))} 
                    style={{ width: '60px', marginLeft: '8px', padding: '4px', background: '#111', color: '#fff', border: '1px solid #444' }}
                  />
                </label>
                <button onClick={handleAddTextVector} className="btn-secondary" style={{ width: '100%', marginTop: '6px', background: '#e91e63', color: '#fff' }}>
                  ✍️ Generate Text Vector
                </button>
              </div>

              <hr />
              <h2>4. Export & CorelDRAW</h2>
              <a 
                href={`${API_BASE}/projects/${projectId}/export/svg`} 
                target="_blank" 
                rel="noreferrer"
                className="btn-export"
              >
                📥 Download Clean SVG Vector
              </a>

              <button onClick={handleCdrWorkflow} className="btn-secondary" style={{ marginTop: '10px', background: '#ff9800', color: '#000' }}>
                📐 CorelDRAW (.CDR) Workflow Guide
              </button>
            </>
          )}
        </div>

        {/* Right Panel: Preview & Cut Ready Checker */}
        <div className="panel preview-panel">
          <h2>Live Production Preview</h2>
          <div className="preview-canvas">
            {file ? (
              <div className="file-info">
                <p><strong>Loaded File:</strong> {file.name}</p>
                <p><strong>Dimensions:</strong> {widthMm} mm × {heightMm} mm</p>
                <p className="secure-badge">🔒 Original preserved securely on disk</p>
              </div>
            ) : (
              <p className="placeholder-text">No artwork loaded. Upload a file to begin.</p>
            )}
          </div>

          {cdrGuide && (
            <div className="checker-results" style={{ borderColor: '#ff9800' }}>
              <h3>{cdrGuide.format}</h3>
              <p style={{ color: '#ffb74d', fontSize: '0.9rem' }}>{cdrGuide.notice}</p>
              <ul style={{ paddingLeft: '15px' }}>
                {cdrGuide.steps.map((step: string, idx: number) => (
                  <li key={idx} style={{ color: '#e0e0e0', marginBottom: '4px' }}>{step}</li>
                ))}
              </ul>
            </div>
          )}

          {traceResult && (
            <div className="checker-results" style={{ borderColor: '#00bcd4' }}>
              <h3>Vector Generation Result</h3>
              <p style={{ color: '#81c784' }}>{traceResult.message}</p>
              {traceResult.contours_traced !== undefined && (
                <p><strong>Contours Extracted:</strong> {traceResult.contours_traced}</p>
              )}
            </div>
          )}

          {checkerReport && (
            <div className="checker-results">
              <h3>Cut Ready Checker Report</h3>
              <ul>
                {Object.entries(checkerReport).map(([key, val]: [string, any]) => (
                  <li key={key} className={val.startsWith("PASS") ? "pass" : "warning"}>
                    <strong>{key.replace(/_/g, " ")}:</strong> {val}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}