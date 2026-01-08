import React, { useEffect } from 'react';
import styles from './Home.module.scss';
import { useState } from 'react';
import api from '../../utils/api';

type RecordItem = {
  id: number;
  name: string;
  created_at: string;
};

const HomePage = () => {
  const [data, setData] = useState<RecordItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // TODO: Replace this with your API
    const fetchData = async () => {
      try {
        setLoading(true);
        const resp = await api.getData();
        setData(resp.data || []);
        setError(null);
      } catch (err) {
        console.error('Failed to fetch data:', err);
        setError('Failed to load data. Please try again later.');
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  return (
    <div className={styles.container}>
      {/* Main Content */}
      <div className={styles.main}>
        <h1>Full-Stack Starter Dashboard</h1>
        <p>
          This is a simple starter page that fetches data from the API. Replace it with your app.
        </p>

        {loading && <p>Loading…</p>}
        {error && <p role="alert">{error}</p>}

        {/* Summary Section */}
        <div className={styles.summary}>
          <h3>Summary KPIs</h3>
          {/* TODO: Render summary numbers here */}
        </div>

        {/* Data Section */}
        <div className={styles.summary}>
          <h3>Records</h3>
          <ul data-testid="records-list">
            {loading && <li>Loading records…</li>}
            {!loading && error && <li>Unable to load records.</li>}
            {!loading &&
              !error &&
              data.map((row) => (
                <li key={row.id}>{row.name}</li>
              ))}
          </ul>
        </div>

        {/* Charts Section */}
        <div className={styles.charts}>
          <h3>Performance Chart</h3>
          {/* TODO: Render LineChart, BarChart and other charts using any chart library */}
        </div>
      </div>
    </div>
  );
};

export default HomePage;
