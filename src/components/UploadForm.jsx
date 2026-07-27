import { useState } from "react";
import { uploadContract } from "../api/contractApi";

function UploadForm() {
  const [url, setUrl] = useState("");
  const [file, setFile] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();

    const formData = new FormData();

    if (url) {
      formData.append("url", url);
    }

    if (file) {
      formData.append("file", file);
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