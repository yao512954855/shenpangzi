'use client';

import { useState, useEffect } from 'react';

interface FileItem {
  id: string;
  file: File;
}

interface ServerFile {
  name: string;
}

interface AnalysisResultItem {
  product_name: string;
  delivery_date: string;
  price_variations: number[];
  sources: {
    file_name: string;
    order_unit: string;
    price: number;
  }[];
}

export default function Home() {
  const [fileItems, setFileItems] = useState<FileItem[]>([]);
  const [serverFiles, setServerFiles] = useState<ServerFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isFetching, setIsFetching] = useState(false);
  const [message, setMessage] = useState('');
  const [analysisResult, setAnalysisResult] = useState<AnalysisResultItem[] | null>(null);

  // 获取服务器上的文件列表
  const fetchServerFiles = async () => {
    setIsFetching(true);
    try {
      const response = await fetch('http://localhost:8000/files');
      const data = await response.json();
      setServerFiles(data.files.map((filename: string) => ({ name: filename })));
    } catch (error) {
      setMessage('获取文件列表失败: ' + (error instanceof Error ? error.message : '未知错误'));
    } finally {
      setIsFetching(false);
    }
  };

  // 组件加载时获取文件列表
  useEffect(() => {
    fetchServerFiles();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    
    if (selectedFiles.length + fileItems.length > 100) {
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
    
    const newFileItems = selectedFiles.map(file => ({
      id: Math.random().toString(36).substr(2, 9),
      file
    }));
    
    setFileItems(prev => [...prev, ...newFileItems]);
  };

  const handleRemoveLocalFile = (id: string) => {
    setFileItems(prev => prev.filter(item => item.id !== id));
  };

  const handleRemoveServerFile = async (filename: string) => {
    try {
      const response = await fetch(`http://localhost:8000/delete/${encodeURIComponent(filename)}`, {
        method: 'DELETE'
      });
      
      const data = await response.json();
      
      if (response.ok) {
        setMessage(data.message);
        await fetchServerFiles(); // 刷新文件列表
      } else {
        throw new Error(data.detail || '删除失败');
      }
    } catch (error) {
      setMessage('删除文件时出错: ' + (error instanceof Error ? error.message : '未知错误'));
    }
  };

  const handleClearAllLocal = () => {
    setFileItems([]);
    const fileInput = document.getElementById('fileInput') as HTMLInputElement;
    if (fileInput) fileInput.value = '';
  };



  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
  
  if (fileItems.length === 0) {
    setMessage('请选择至少一个文件');
    return;
  }
  
  setIsUploading(true);
  setMessage('');
  
  try {
    const formData = new FormData();
    fileItems.forEach(item => {
      formData.append('files', item.file);
    });
    
    const response = await fetch('http://localhost:8000/upload', {
      method: 'POST',
      body: formData,
    });
    
    const data = await response.json();
    
    if (response.ok) {
      setMessage(data.message);
      setFileItems([]);
      const fileInput = document.getElementById('fileInput') as HTMLInputElement;
      if (fileInput) fileInput.value = '';
      
      // 显示处理结果
      if (data.process_results) {
        const successCount = data.process_results.filter((r: any) => r.saved_to_db).length;
        const errorCount = data.process_results.length - successCount;
        
        setMessage(`处理完成: ${successCount}个成功, ${errorCount}个失败`);
        
        // 显示失败的文件和原因
        const errorFiles = data.process_results.filter((r: any) => r.error);
        if (errorFiles.length > 0) {
          setMessage(prev => prev + '\n失败文件: ' + 
            errorFiles.map((f: any) => `${f.file_name}: ${f.error}`).join('; '));
        }
      }
      
      await fetchServerFiles();
    } else {
      throw new Error(data.detail || '上传失败');
    }
  } catch (error) {
    setMessage('上传过程中出错: ' + (error instanceof Error ? error.message : '未知错误'));
  } finally {
    setIsUploading(false);
  }
};

  return (
    <div style={{ 
      minHeight: '100vh',
      backgroundColor: 'black',
      color: 'white',
      padding: '2rem',
      fontFamily: 'system-ui, sans-serif'
    }}>
      <main style={{ 
        maxWidth: '800px',
        margin: '0 auto',
        textAlign: 'center'
      }}>
        <h1 style={{
          fontSize: '3rem',
          fontWeight: 'bold',
          marginBottom: '2rem',
          letterSpacing: '0.1em'
        }}>
          Excel 文件上传系统
        </h1>

        {/* 文件上传表单 */}
        <div style={{ 
          backgroundColor: '#1a1a1a',
          padding: '2rem',
          borderRadius: '8px',
          marginBottom: '2rem'
        }}>
          <h2 style={{ marginTop: 0 }}>上传新文件</h2>
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
                padding: '12px 24px',
                backgroundColor: 'white',
                color: 'black',
                borderRadius: '8px',
                cursor: 'pointer',
                fontSize: '1.1rem',
                fontWeight: '600',
                transition: 'all 0.2s',
                marginRight: '1rem'
              }}>
                选择 Excel 文件
              </label>
              <span style={{ fontSize: '1.1rem' }}>
                已选择 {fileItems.length} 个文件
              </span>
            </div>
            
            {fileItems.length > 0 && (
              <div style={{ 
                marginBottom: '1.5rem',
                backgroundColor: '#2a2a2a',
                padding: '1rem',
                borderRadius: '8px',
                maxHeight: '300px',
                overflowY: 'auto'
              }}>
                <div style={{ 
                  display: 'flex', 
                  justifyContent: 'space-between', 
                  alignItems: 'center',
                  marginBottom: '1rem'
                }}>
                  <h3 style={{ margin: 0 }}>待上传文件:</h3>
                  <button
                    type="button"
                    onClick={handleClearAllLocal}
                    style={{
                      padding: '6px 12px',
                      backgroundColor: '#ff4444',
                      color: 'white',
                      border: 'none',
                      borderRadius: '4px',
                      cursor: 'pointer',
                      fontSize: '0.9rem'
                    }}
                  >
                    清空所有
                  </button>
                </div>
                
                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                  {fileItems.map((item) => (
                    <li key={item.id} style={{ 
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '0.75rem',
                      borderBottom: '1px solid #333',
                      backgroundColor: '#3a3a3a',
                      marginBottom: '0.5rem',
                      borderRadius: '4px'
                    }}>
                      <span style={{ 
                        flex: 1, 
                        textAlign: 'left',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                        whiteSpace: 'nowrap'
                      }}>
                        {item.file.name}
                      </span>
                      <span style={{ 
                        fontSize: '0.9rem',
                        color: '#888',
                        marginLeft: '1rem'
                      }}>
                        {(item.file.size / 1024).toFixed(1)} KB
                      </span>
                      <button
                        type="button"
                        onClick={() => handleRemoveLocalFile(item.id)}
                        style={{
                          marginLeft: '1rem',
                          padding: '4px 8px',
                          backgroundColor: '#ff4444',
                          color: 'white',
                          border: 'none',
                          borderRadius: '4px',
                          cursor: 'pointer',
                          fontSize: '0.8rem'
                        }}
                      >
                        删除
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            
            <button
              type="submit"
              disabled={isUploading || fileItems.length === 0}
              style={{
                padding: '12px 32px',
                backgroundColor: isUploading || fileItems.length === 0 ? '#666' : '#0070f3',
                color: 'white',
                border: 'none',
                borderRadius: '8px',
                cursor: isUploading || fileItems.length === 0 ? 'not-allowed' : 'pointer',
                fontSize: '1.1rem',
                fontWeight: '600',
                transition: 'all 0.2s'
              }}
            >
              {isUploading ? '上传中...' : '开始上传'}
            </button>
          </form>
        </div>

        {/* 已上传文件列表 */}
        <div style={{ 
          backgroundColor: '#1a1a1a',
          padding: '2rem',
          borderRadius: '8px'
        }}>
          <h2 style={{ marginTop: 0 }}>已上传文件</h2>
          {isFetching ? (
            <p>加载中...</p>
          ) : serverFiles.length === 0 ? (
            <p>暂无已上传文件</p>
          ) : (
            <div style={{ 
              backgroundColor: '#2a2a2a',
              padding: '1rem',
              borderRadius: '8px',
              maxHeight: '400px',
              overflowY: 'auto'
            }}>
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {serverFiles.map((file, index) => (
                  <li key={index} style={{ 
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.75rem',
                    borderBottom: '1px solid #333',
                    backgroundColor: '#3a3a3a',
                    marginBottom: '0.5rem',
                    borderRadius: '4px'
                  }}>
                    <span style={{ 
                      flex: 1, 
                      textAlign: 'left',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap'
                    }}>
                      {file.name}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleRemoveServerFile(file.name)}
                      style={{
                        marginLeft: '1rem',
                        padding: '4px 8px',
                        backgroundColor: '#ff4444',
                        color: 'white',
                        border: 'none',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '0.8rem'
                      }}
                    >
                      删除
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
        
        {message && (
          <div style={{
            padding: '1rem',
            backgroundColor: message.includes('成功') ? '#2e7d32' : '#d32f2f',
            color: 'white',
            borderRadius: '8px',
            marginTop: '2rem'
          }}>
            {message}
          </div>
        )}
        
        {analysisResult && analysisResult.length > 0 && (
          <div style={{ 
            backgroundColor: '#ff4444',
            padding: '2rem',
            borderRadius: '8px',
            marginTop: '2rem'
          }}>
            <h2 style={{ marginTop: 0, color: 'white' }}>⚠️ 价格不一致警告</h2>
            <p style={{ color: 'white' }}>发现以下商品在不同送货单中存在价格不一致：</p>
            
            {analysisResult.map((item, index) => (
              <div key={index} style={{ 
                backgroundColor: 'rgba(255, 255, 255, 0.1)',
                padding: '1rem',
                borderRadius: '8px',
                marginBottom: '1rem'
              }}>
                <h3 style={{ color: 'white', margin: '0 0 0.5rem 0' }}>
                  商品: {item.product_name}
                </h3>
                <p style={{ color: 'white', margin: '0 0 0.5rem 0' }}>
                  送货日期: {item.delivery_date}
                </p>
                <p style={{ color: 'white', margin: '0 0 0.5rem 0' }}>
                  价格变化: {item.price_variations.join(', ')}
                </p>
                
                <h4 style={{ color: 'white', margin: '0 0 0.5rem 0' }}>来源文件:</h4>
                <ul style={{ color: 'white', paddingLeft: '1rem' }}>
                  {item.sources.map((source, sourceIndex) => (
                    <li key={sourceIndex}>
                      {source.file_name} - {source.order_unit} - 价格: {source.price}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}