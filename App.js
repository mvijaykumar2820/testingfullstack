import React, { useState, useRef, useEffect } from "react";
import "./App.css";

function App() {
  const [url, setUrl] = useState("");
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [progress, setProgress] = useState(0);
  const [status, setStatus] = useState("");
  const summaryRef = useRef(null);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    const currentEventSource = eventSourceRef.current;
  
    return () => {
      if (currentEventSource) {
        currentEventSource.close();
      }
    };
  }, []);

  const handleSummarize = async () => {
    if (!url) {
      setError("Please enter a YouTube URL!");
      return;
    }

    // Validate YouTube URL format (basic validation)
    const youtubeRegex = /^(https?:\/\/)?(www\.)?(youtube\.com|youtu\.?be)\/.+$/;
    if (!youtubeRegex.test(url)) {
      setError("Please enter a valid YouTube URL");
      return;
    }

    setLoading(true);
    setSummary("");
    setError("");
    setProgress(0);
    setStatus("Initializing...");

    // Close any existing SSE connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    try {
      // Send initial request to start the process
      const response = await fetch("http://localhost:5000/summarize", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ url }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      // Set up event source for streaming updates
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      
      const processStreamChunks = async () => {
        try {
          while (true) {
            const { done, value } = await reader.read();
            
            if (done) {
              break;
            }
            
            const text = decoder.decode(value);
            const lines = text.split('\n\n');
            
            for (const line of lines) {
              if (line.startsWith('data: ')) {
                try {
                  const data = JSON.parse(line.slice(5));
                  
                  // Handle progress updates
                  if (data.progress !== undefined) {
                    setProgress(data.progress);
                  }
                  
                  // Handle status updates
                  if (data.status) {
                    setStatus(data.status);
                  }
                  
                  // Handle summary
                  if (data.summary) {
                    setSummary(data.summary);
                    setLoading(false);
                    setProgress(100);
                  }
                  
                  // Handle errors
                  if (data.error) {
                    setError(data.error);
                    setLoading(false);
                  }
                } catch (e) {
                  console.error("Error parsing SSE data:", e);
                }
              }
            }
          }
        } catch (e) {
          console.error("Error reading stream:", e);
          setError("Error receiving updates from server");
          setLoading(false);
        }
      };
      
      processStreamChunks();
    } catch (err) {
      console.error("Error:", err);
      setError("Something went wrong on the server. Please try again later.");
      setLoading(false);
    }
  };

  const copyToClipboard = () => {
    if (summaryRef.current) {
      navigator.clipboard.writeText(summary)
        .then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 3000);
        })
        .catch(err => {
          console.error("Could not copy text: ", err);
        });
    }
  };

  return (
    <div className="app-container">
      <div className="header">
        <h1>YouTube Video Summarizer</h1>
        <p>Get concise summaries of any YouTube video in seconds</p>
      </div>

      <div className="input-section">
        <input
          type="text"
          className="url-input"
          placeholder="Paste YouTube URL here..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
        <button 
          className="summarize-btn" 
          onClick={handleSummarize} 
          disabled={loading}
        >
          {loading ? "Analyzing..." : "Summarize Video"}
        </button>
      </div>

      {error && <div className="error-message">{error}</div>}

      {loading && (
        <div className="analysis-container">
          <h3 className="analysis-title">Analyzing Video Content</h3>
          
          <div className="progress-bar-container">
            <div 
              className="progress-bar" 
              style={{ width: `${progress}%` }}
            ></div>
          </div>
          
          <div className="progress-percentage">{Math.round(progress)}%</div>
          
          <div className="analysis-status">
            <p>{status}</p>
          </div>
          
          <div className="analysis-dots">
            <div className="dot"></div>
            <div className="dot"></div>
            <div className="dot"></div>
          </div>
        </div>
      )}

      {summary && (
        <div className="summary-container">
          <div className="summary-header">
            <h3 className="summary-title">Video Summary</h3>
            <button className="copy-btn" onClick={copyToClipboard}>
              Copy to Clipboard
            </button>
          </div>
          <div className="summary-content" ref={summaryRef}>
            {summary.split('\n').map((paragraph, index) => (
              paragraph.trim() ? <p key={index}>{paragraph}</p> : null
            ))}
          </div>
        </div>
      )}

      {copied && (
        <div className="success-message">
          Summary copied to clipboard!
        </div>
      )}
    </div>
  );
}

export default App;