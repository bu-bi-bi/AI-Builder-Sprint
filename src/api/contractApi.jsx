export async function uploadContract(formData) {
  const response = await fetch("http://localhost:8080/analyze", {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error("API 요청 실패");
  }

  return response.json();
}