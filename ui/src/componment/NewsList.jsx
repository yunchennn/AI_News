import { useEffect, useState } from "react";

function NewsList() {
  const [summaries, setSummaries] = useState([]);
  const [loading, setLoading] = useState(true);  // 新增一個 loading 狀態

  useEffect(() => {
    fetch("http://127.0.0.1:8000/summaries")
      .then((response) => response.json())
      .then((data) => {
        setSummaries(data);
        setLoading(false);  // 資料拿到後，更新 loading 狀態
      })
      .catch((error) => {
        console.error("Error fetching summaries:", error);
        setLoading(false);  // 資料錯誤，也停止 loading 狀態
      });
  }, []);

  return (
    <div className="min-h-screen bg-gray-100 p-8">
      <h1 className="text-3xl font-bold mb-6 text-center text-gray-800">📰 News Summaries</h1>

      {loading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full border-t-4 border-blue-600 w-12 h-12"></div>
        </div>
      ) : (
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {summaries.map((summary) => (
            <div
              key={summary.id}
              className="bg-white rounded-2xl shadow-md p-6 hover:shadow-lg transition"
            >
              <h2 className="text-xl font-semibold text-gray-900 mb-2">{summary.llm_title}</h2>
              <p className="text-lg font-semibold text-gray-700 mb-2">
                {new Date(summary.report_timestamp).toISOString().slice(0, 16).replace('T', ' ')}
              </p>

              <p className="text-gray-600 text-sm">{summary.summary}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default NewsList;
