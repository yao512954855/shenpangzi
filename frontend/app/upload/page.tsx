'use client';

import { useState } from 'react';

export default function ExcelUpload() {
  const [files, setFiles] = useState<File[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [message, setMessage] = useState('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    
    if (selectedFiles.length > 100) {
      alert('最多只能上传100个文件');
      return;
    }
    
    const invalidFiles = selectedFiles.filter(
      file => !file.name.endsWith('.xls') && !file.name.endsWith('.xlsx')
    );
    
    if (invalidFiles.length > 0) {
      alert('只能上传.xls或.xlsx文件');
      return;
    }
    
    setFiles(selectedFiles);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    if (files.length === 0) {
      setMessage('请选择至少一个文件');
      return;
    }
    
    setIsUploading(true);
    setMessage('');
    
    try {
      const formData = new FormData();
      files.forEach(file => {
        formData.append('files', file);
      });
      
      const response = await fetch('http://localhost:8000/upload', {
        method: 'POST',
        body: formData,
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setMessage(`成功上传 ${data.files.length} 个文件`);
        setFiles([]);
        const fileInput = document.getElementById('fileInput') as HTMLInputElement;
        if (fileInput) fileInput.value = '';
      } else {
        setMessage(data.detail || '上传失败');
      }
    } catch (error) {
      setMessage('上传过程中出错: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div style={{ maxWidth: '600px', margin: '0 auto', padding: '2rem' }}>
      <h1>Excel 文件上传</h1>
      <form onSubmit={handleSubmit}>
        <div style={{ marginBottom: '1.5rem' }}>
          <input
            type="file"
            id="fileInput"
            multiple
            accept=".xls,.xlsx"
            onChange={handleFileChange}
            style={{ display: 'none' }}
          />
          <label htmlFor="fileInput" style={{
            display: 'inline-block',
            padding: '0.5rem 1rem',
            backgroundColor: '#0070f3',
            color: 'white',
            borderRadius: '4px',
            cursor: 'pointer',
            transition: 'background-color 0.2s'
          }}>
            选择文件 (最多100个)
          </label>
          <span style={{ marginLeft: '1rem' }}>
            {files.length > 0 ? `已选择 ${files.length} 个文件` : '未选择文件'}
          </span>
        </div>
        
        {files.length > 0 && (
          <div style={{ marginBottom: '1.5rem' }}>
            <h3>选中的文件:</h3>
            <ul style={{ 
              maxHeight: '200px', 
              overflowY: 'auto', 
              border: '1px solid #ddd', 
              padding: '1rem',
              listStyleType: 'none'
            }}>
              {files.map((file, index) => (
                <li key={index}>{file.name}</li>
              ))}
            </ul>
          </div>
        )}
        
        <button
          type="submit"
          disabled={isUploading || files.length === 0}
          style={{
            padding: '0.5rem 1rem',
            backgroundColor: isUploading || files.length === 0 ? '#ccc' : '#0070f3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isUploading || files.length === 0 ? 'not-allowed' : 'pointer'
          }}
        >
          {isUploading ? '上传中...' : '上传文件'}
        </button>
      </form>
      
      {message && (
        <div style={{
          marginTop: '1.5rem',
          padding: '1rem',
          backgroundColor: message.includes('成功') ? '#e6ffed' : '#ffebee',
          border: `1px solid ${message.includes('成功') ? '#a3d8b1' : '#f5c6cb'}`,
          borderRadius: '4px'
        }}>
          {message}
        </div>
      )}
    </div>
  );
}