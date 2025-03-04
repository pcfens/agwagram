import React, { useContext, useEffect, useState } from "react";
import style from "./Analyze.module.scss";
import SearchInput from "../components/SearchInput";
import FileUploadPortal from "../components/FileUploadPortal";
import { AnalysisContext } from "../contexts/AnalysisContext";
import { API_URL } from "../Global";
import Results from "./Results";

const Analyze: React.FC = () => {
  const { results, setResults } = useContext(AnalysisContext);
  const [displayResults, setDisplayResults] = useState<boolean>(false);

  async function uploadFiles(url: string = "", files: File[]) {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("tweet_files", file);
    });

    const response = await fetch(url, {
      method: "POST",
      body: formData,
    });
    return response.json();
  }

  const submitFiles = (files: File[]) => {
    console.log(files);
    uploadFiles(`${API_URL}/analyze/file`, files).then((data) => {
      setResults(data);
    });
  };

  async function analyzeUsername(url: string = "", username: string) {
    const response = await fetch(`${url}?username=${username}`, {
      method: "GET",
    });
    return response.json();
  }

  const searchUsername = (input: string) => {
    analyzeUsername(`${API_URL}/analyze/user`, input).then((data) => {
      setResults(data);
    });
  };

  useEffect(() => {
    setDisplayResults(results)
  }, [results]);

  return !displayResults ? (
    <div className={style.content}>
      <h1>Analyze</h1>
      <div className={style.columns}>
        <div>
          <h3>Analyze By Username</h3>
          <p>
            Search for one or more accounts (separated by a comma) by their
            current Twitter username.
          </p>
          <SearchInput submit={searchUsername} />
        </div>
        <div>
          <h3>Analyze By File</h3>
          <p>
            Upload files containing Tweet data to be analyzed using the BLOC
            algorithm. Files can be in <strong>JSON</strong> or{" "}
            <strong>JSONL</strong> formats and can be uploaded unzipped or as
            Gzip files. To upload multiple files at once please select them all
            in the file selection prompt or drag-and-drop them each in.
          </p>
          <p>
            <strong>Note:</strong> JSON files are expected to contain the Tweet
            data as an array of Tweet objects, while the JSONL files are
            expected to be formatted with each line being a Tweet, <em>not</em>{" "}
            an account.
          </p>
          <FileUploadPortal submit={submitFiles} />
        </div>
      </div>
    </div>
  ) : <Results/>;
};

export default Analyze;
