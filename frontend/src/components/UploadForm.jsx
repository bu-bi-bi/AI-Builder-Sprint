import { useState } from "react";
import { uploadContract } from "../api/contractApi";

function UploadForm() {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);
  const [upstreamApiKey, setUpstreamApiKey] = useState("");
  const [modusignApiKey, setModusignApiKey] = useState("");

  const handleSubmit = async (e) => {
    e.preventDefault();

    const formData = new FormData();

    if (url) {
      formData.append("url", url);
    }

    if (file) {
      formData.append("file", file);
    }

    if (upstreamApiKey) {
      formData.append("upstreamApiKey", upstreamApiKey);
    }

    if (modusignApiKey) {
      formData.append("modusignApiKey", modusignApiKey);
    }

    try {
      const result = await uploadContract(formData);

      console.log(result);
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>URL</label>

        <input
          type="url"
          placeholder="https://..."
          value={url}
          onChange={(e) => setUrl(e.target.value)}
        />
      </div>

      <div>
        <label>Upstream API Key</label>

        <input
          type="password"
          placeholder="Enter upstream API key"
          value={upstreamApiKey}
          onChange={(e) => setUpstreamApiKey(e.target.value)}
        />
      </div>

      <div>
        <label>Modusign API Key</label>

        <input
          type="password"
          placeholder="Enter modusign API key"
          value={modusignApiKey}
          onChange={(e) => setModusignApiKey(e.target.value)}
        />
      </div>

      <div>
        <label>파일 업로드</label>

        <input
          type="file"
          onChange={(e) => setFile(e.target.files[0])}
        />
      </div>

      <button type="submit">
        분석 시작
      </button>
    </form>
  );
}

export default UploadForm;