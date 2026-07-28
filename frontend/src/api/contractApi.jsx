export async function uploadContract(formData) {

  const response = await fetch("http://127.0.0.1:8000/contractsParsing", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("API 요청 실패");
  }

  return response.json();
}