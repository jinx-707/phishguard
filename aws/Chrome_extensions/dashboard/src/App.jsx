/**
 * PhishGuard Enterprise SOC Dashboard
 * React Frontend - Main Dashboard Application
 * Retro Cyber Arcade Theme
 */

import React, { useState, useEffect, useCallback } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './dashboard.css';

// API Base URL - uses relative path for proxy support
const API_BASE = '';

// ============== LOGO COMPONENT ==============

function CyberLogo() {
  return (
    <div className="cyber-logo">
      <div className="logo-text">PHISHGUARD</div>
      <div className="logo-subtitle">THREAT INTELLIGENCE</div>
    </div>
  );
}

// ============== AUTH CONTEXT ==============

const AuthContext = React.createContext(null);

function useAuth() {
  return React.useContext(AuthContext);
}

// ============== LOGIN COMPONENT ==============

function Login({ onLogin }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    try {
      const formData = new URLSearchParams();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: formData
      });

      if (!response.ok) {
        throw new Error('Invalid credentials');
      }

      const data = await response.json();
      onLogin(data.access_token, data.user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <CyberLogo />
      <div className="login-box">
        <div className="login-header-decoration">
          <span className="decorative-bracket">[</span>
          <span className="login-title">ACCESS TERMINAL</span>
          <span className="decorative-bracket">]</span>
        </div>
        
        <form onSubmit={handleSubmit}>
          <div className="input-wrapper">
            <span className="input-prompt">></span>
            <input
              type="text"
              placeholder="USERNAME"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>
          <div className="input-wrapper">
            <span className="input-prompt">></span>
            <input
              type="password"
              placeholder="PASSWORD"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          {error && <div className="error">ERROR: {error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? 'AUTHENTICATING...' : 'INITIATE ACCESS'}
          </button>
        </form>
        
        <div className="demo-credentials">
          <p>CREDENTIALS: admin / admin123</p>
        </div>
      </div>
    </div>
  );
}

// ============== SIDEBAR ==============

function Sidebar({ activeView, setActiveView, user, onLogout }) {
  const menuItems = [
    { id: 'overview', label: '[DASHBOARD]' },
    { id: 'live-threats', label: '[LIVE THREATS]' },
    { id: 'campaigns', label: '[CAMPAIGNS]' },
    { id: 'graph', label: '[INFRASTRUCTURE]' },
    { id: 'endpoints', label: '[ENDPOINTS]' },
    { id: 'trends', label: '[TRENDS]' },
    { id: 'investigate', label: '[INVESTIGATE]' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <CyberLogo />
      </div>
      
      <nav className="sidebar-nav">
        {menuItems.map(item => (
          <button
            key={item.id}
            className={`nav-item ${activeView === item.id ? 'active' : ''}`}
            onClick={() => setActiveView(item.id)}
          >
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
      
      <div className="sidebar-footer">
        <div className="user-info">
          <span className="user-label">USER:</span>
          <span className="user-name">{user?.full_name || 'ADMIN'}</span>
          <span className="user-role">{user?.role || 'operator'}</span>
        </div>
        <button className="logout-btn" onClick={onLogout}>[TERMINATE]</button>
      </div>
    </aside>
  );
}

// ============== OVERVIEW DASHBOARD ==============

function OverviewDashboard({ token }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [currentTime, setCurrentTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/summary`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setSummary(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="loading">INITIALIZING DASHBOARD...</div>;

  return (
    <div className="dashboard-grid">
      <div className="stat-card primary">
        <h3>[ THREATS BLOCKED TODAY ]</h3>
        <div className="stat-value">{summary?.total_threats_blocked_today?.toLocaleString() || 0}</div>
        <div className="stat-trend positive">[+12% FROM YESTERDAY]</div>
      </div>
      
      <div className="stat-card warning">
        <h3>[ ACTIVE CAMPAIGNS ]</h3>
        <div className="stat-value">{summary?.active_campaigns || 0}</div>
        <div className="stat-trend">[REQUIRES ATTENTION]</div>
      </div>
      
      <div className="stat-card danger">
        <h3>[ ZERO-DAY DETECTIONS ]</h3>
        <div className="stat-value">{summary?.zero_day_detections || 0}</div>
        <div className="stat-trend negative">[+3 NEW TODAY]</div>
      </div>
      
      <div className="stat-card success">
        <h3>[ ENDPOINTS PROTECTED ]</h3>
        <div className="stat-value">{summary?.endpoints_protected?.toLocaleString() || 0}</div>
        <div className="stat-trend positive">[+24 THIS HOUR]</div>
      </div>

      <div className="card wide">
        <h3>> TOP TARGETED BRANDS</h3>
        <div className="brand-list">
          {summary?.top_targeted_brands?.map((brand, i) => (
            <div key={i} className="brand-item">
              <span className="brand-name">{brand.brand}</span>
              <div className="brand-bar">
                <div 
                  className="brand-fill" 
                  style={{ width: `${(brand.attempts / summary.top_targeted_brands[0].attempts) * 100}%` }}
                />
              </div>
              <span className="brand-count">[{brand.attempts}]</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card wide">
        <h3>> RECENT ACTIVITY LOG</h3>
        <div className="activity-list">
          {summary?.recent_activity?.map((activity, i) => (
            <div key={i} className={`activity-item ${activity.severity}`}>
              <span className="activity-time">[{activity.time}]</span>
              <span className="activity-event">{activity.event}</span>
              <span className={`severity-badge ${activity.severity}`}>{activity.severity.toUpperCase()}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card wide">
        <h3>> SYSTEM STATUS</h3>
        <div className="system-status">
          <div className="status-row">
            <span className="status-label">SYSTEM TIME:</span>
            <span className="status-value">{currentTime.toISOString().slice(0, 19).replace('T', ' ')}</span>
          </div>
          <div className="status-row">
            <span className="status-label">API STATUS:</span>
            <span className="status-value online">[ONLINE]</span>
          </div>
          <div className="status-row">
            <span className="status-label">SCAN ENGINE:</span>
            <span className="status-value online">[ACTIVE]</span>
          </div>
          <div className="status-row">
            <span className="status-label">THREAT DB:</span>
            <span className="status-value online">[UPDATED]</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============== LIVE THREATS ==============

function LiveThreats({ token }) {
  const [threats, setThreats] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());

  const fetchThreats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/live-threats?limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setThreats(data);
      setLastUpdate(new Date());
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchThreats();
    const interval = setInterval(fetchThreats, 3000);
    return () => clearInterval(interval);
  }, [fetchThreats]);

  const getSourceColor = (source) => {
    const colors = { 'GNN': '#8b5cf6', 'NLP': '#3b82f6', 'DOM': '#f97316', 'INFRA': '#22c55e' };
    return colors[source] || '#6b7280';
  };

  if (loading) return <div className="loading">LOADING THREAT FEED...</div>;

  return (
    <div className="live-threats">
      <div className="section-header">
        <h2>> LIVE THREAT FEED</h2>
        <span className="live-indicator">SCANNING</span>
        <span className="last-update">LAST UPDATE: {lastUpdate.toLocaleTimeString()}</span>
      </div>
      
      <div className="threats-table">
        <table>
          <thead>
            <tr>
              <th>> DOMAIN</th>
              <th>> RISK SCORE</th>
              <th>> CONFIDENCE</th>
              <th>> SOURCE</th>
              <th>> CAMPAIGN</th>
              <th>> TIMESTAMP</th>
            </tr>
          </thead>
          <tbody>
            {threats.map(threat => (
              <tr key={threat.id} className="threat-row">
                <td className="domain-cell">
                  <span className="domain-name">{threat.domain}</span>
                </td>
                <td>
                  <div className="score-bar">
                    <div 
                      className="score-fill" 
                      style={{ width: `${threat.risk_score * 100}%` }}
                    />
                    <span className="score-value">{(threat.risk_score * 100).toFixed(0)}%</span>
                  </div>
                </td>
                <td>{(threat.confidence * 100).toFixed(0)}%</td>
                <td>
                  <span 
                    className="source-badge"
                    style={{ backgroundColor: getSourceColor(threat.detection_source) }}
                  >
                    {threat.detection_source}
                  </span>
                </td>
                <td>{threat.campaign_id || '--'}</td>
                <td className="time-cell">{new Date(threat.timestamp).toLocaleTimeString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ============== CAMPAIGNS VIEW ==============

function CampaignsView({ token }) {
  const [campaigns, setCampaigns] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/campaigns`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setCampaigns(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="loading">LOADING CAMPAIGN DATA...</div>;

  return (
    <div className="campaigns-view">
      <h2>> CAMPAIGN INTELLIGENCE</h2>
      
      <div className="campaigns-grid">
        {campaigns.map(campaign => (
          <div key={campaign.campaign_id} className="campaign-card">
            <div className="campaign-header">
              <h3>{campaign.campaign_id}</h3>
              <span className={`trend-badge ${campaign.growth_trend}`}>
                {campaign.growth_trend === 'growing' ? '[GROWING]' : '[STABLE]'}
              </span>
            </div>
            
            <div className="campaign-stats">
              <div className="campaign-stat">
                <span className="stat-label">CLUSTER SIZE</span>
                <span className="stat-value">{campaign.cluster_size} DOMAINS</span>
              </div>
              <div className="campaign-stat">
                <span className="stat-label">AVG RISK</span>
                <span className="stat-value">{(campaign.avg_risk_score * 100).toFixed(0)}%</span>
              </div>
            </div>
            
            <div className="campaign-infra">
              <h4>> SHARED INFRASTRUCTURE</h4>
              <div className="infra-item">
                <span className="infra-label">IP:</span>
                <span className="infra-value">{campaign.shared_ip}</span>
              </div>
              <div className="infra-item">
                <span className="infra-label">CERT:</span>
                <span className="infra-value">{campaign.shared_cert}</span>
              </div>
            </div>
            
            <div className="campaign-domains">
              <h4>> DOMAINS ({campaign.domains.length})</h4>
              <ul>
                {campaign.domains.slice(0, 3).map((domain, i) => (
                  <li key={i}>{domain}</li>
                ))}
                {campaign.domains.length > 3 && (
                  <li className="more">+{campaign.domains.length - 3} MORE</li>
                )}
              </ul>
            </div>
            
            <div className="campaign-footer">
              <span className="first-seen">FIRST SEEN: {new Date(campaign.first_seen).toLocaleDateString()}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============== INFRASTRUCTURE GRAPH ==============

function InfrastructureGraph({ token }) {
  const [graphData, setGraphData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [selectedNode, setSelectedNode] = useState(null);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/graph`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setGraphData(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  const getNodeColor = (type, risk) => {
    if (risk > 0.7) return '#ef4444';
    if (risk > 0.4) return '#f97316';
    return '#22c55e';
  };

  if (loading) return <div className="loading">LOADING INFRASTRUCTURE MAP...</div>;

  const nodes = graphData?.nodes?.map((node, i) => ({
    ...node,
    x: 100 + (i % 4) * 200,
    y: 100 + Math.floor(i / 4) * 150
  })) || [];

  return (
    <div className="graph-view">
      <h2>> INFRASTRUCTURE GRAPH</h2>
      
      <div className="graph-container">
        <svg viewBox="0 0 800 600" className="graph-svg">
          <defs>
            <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
              <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#0B2A2A" strokeWidth="1"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />
          
          {graphData?.edges?.map((edge, i) => {
            const source = nodes.find(n => n.id === edge.source);
            const target = nodes.find(n => n.id === edge.target);
            if (!source || !target) return null;
            return (
              <line
                key={i}
                x1={source.x} y1={source.y}
                x2={target.x} y2={target.y}
                stroke="#39FF14"
                strokeWidth="2"
                strokeOpacity="0.3"
              />
            );
          })}
          
          {nodes.map(node => (
            <g 
              key={node.id} 
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => setSelectedNode(node)}
              className="graph-node"
            >
              <circle
                r={node.type === 'domain' ? 25 : 20}
                fill={getNodeColor(node.type, node.risk)}
                stroke="#39FF14"
                strokeWidth="2"
              />
              <text 
                y={node.type === 'domain' ? 40 : 35} 
                textAnchor="middle"
                className="node-label"
              >
                {node.label.length > 15 ? node.label.slice(0, 15) + '...' : node.label}
              </text>
              <text 
                y={5} 
                textAnchor="middle" 
                fill="#fff"
                fontSize="10"
              >
                {node.type === 'domain' ? 'D' : node.type === 'ip' ? 'IP' : 'C'}
              </text>
            </g>
          ))}
        </svg>
      </div>

      {selectedNode && (
        <div className="node-details">
          <h3>> NODE DETAILS</h3>
          <div className="detail-row">
            <span className="label">ID:</span>
            <span className="value">{selectedNode.id}</span>
          </div>
          <div className="detail-row">
            <span className="label">LABEL:</span>
            <span className="value">{selectedNode.label}</span>
          </div>
          <div className="detail-row">
            <span className="label">TYPE:</span>
            <span className="value">{selectedNode.type}</span>
          </div>
          <div className="detail-row">
            <span className="label">RISK:</span>
            <span className="value">{(selectedNode.risk * 100).toFixed(0)}%</span>
          </div>
          <button onClick={() => setSelectedNode(null)}>[CLOSE]</button>
        </div>
      )}
    </div>
  );
}

// ============== ENDPOINTS VIEW ==============

function EndpointsView({ token }) {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/endpoint-stats`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setStats(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="loading">LOADING ENDPOINT STATS...</div>;

  return (
    <div className="endpoints-view">
      <h2>> ENDPOINT STATISTICS</h2>
      
      <div className="endpoint-grid">
        <div className="endpoint-stat">
          <div className="stat-icon">[SYS]</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.total_endpoints?.toLocaleString()}</span>
            <span className="stat-label">TOTAL ENDPOINTS</span>
          </div>
        </div>
        
        <div className="endpoint-stat">
          <div className="stat-icon">[SCAN]</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.scans_per_minute}</span>
            <span className="stat-label">SCANS/MINUTE</span>
          </div>
        </div>
        
        <div className="endpoint-stat danger">
          <div className="stat-icon">[BLK]</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.blocked_attempts?.toLocaleString()}</span>
            <span className="stat-label">BLOCKED ATTEMPTS</span>
          </div>
        </div>
        
        <div className="endpoint-stat warning">
          <div className="stat-icon">[OVR]</div>
          <div className="stat-info">
            <span className="stat-value">{(stats?.override_rate * 100).toFixed(1)}%</span>
            <span className="stat-label">OVERRIDE RATE</span>
          </div>
        </div>
        
        <div className="endpoint-stat info">
          <div className="stat-icon">[OFF]</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.offline_detections}</span>
            <span className="stat-label">OFFLINE DETECTIONS</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// ============== TRENDS VIEW ==============

function TrendsView({ token }) {
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/risk-trends?days=7`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setTrends(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="loading">LOADING TRENDS...</div>;

  const COLORS = ['#39FF14', '#00FF9C', '#00D4FF', '#FF073A', '#FFE135', '#FF6B35'];

  return (
    <div className="trends-view">
      <h2>> RISK TREND ANALYTICS</h2>
      
      <div className="charts-grid">
        <div className="chart-card">
          <h3>> DAILY BLOCKED ATTEMPTS</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0B2A2A" />
              <XAxis dataKey="date" tick={{fontSize: 12, fill: '#39FF14'}} stroke="#39FF14" />
              <YAxis tick={{fontSize: 12, fill: '#39FF14'}} stroke="#39FF14" />
              <Tooltip contentStyle={{ backgroundColor: '#020617', border: '1px solid #39FF14', color: '#39FF14' }} />
              <Line type="monotone" dataKey="blocked_count" stroke="#39FF14" strokeWidth={2} dot={{fill: '#39FF14'}} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        <div className="chart-card">
          <h3>> ZERO-DAY DETECTIONS</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" stroke="#0B2A2A" />
              <XAxis dataKey="date" tick={{fontSize: 12, fill: '#FF073A'}} stroke="#FF073A" />
              <YAxis tick={{fontSize: 12, fill: '#FF073A'}} stroke="#FF073A" />
              <Tooltip contentStyle={{ backgroundColor: '#020617', border: '1px solid #FF073A', color: '#FF073A' }} />
              <Bar dataKey="zero_day_count" fill="#FF073A" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        <div className="chart-card">
          <h3>> CAMPAIGN DISTRIBUTION</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={trends}
                dataKey="new_campaigns"
                nameKey="date"
                cx="50%"
                cy="50%"
                outerRadius={80}
                label={{ fill: '#39FF14' }}
              >
                {trends.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: '#020617', border: '1px solid #39FF14', color: '#39FF14' }} />
              <Legend wrapperStyle={{ color: '#39FF14' }} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}

// ============== INVESTIGATE VIEW ==============

function InvestigateView({ token }) {
  const [searchTerm, setSearchTerm] = useState('');
  const [investigation, setInvestigation] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchTerm) return;
    
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/dashboard/investigate/${searchTerm}`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setInvestigation(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="investigate-view">
      <h2>> ALERT INVESTIGATION</h2>
      
      <form className="search-form" onSubmit={handleSearch}>
        <div className="search-input-wrapper">
          <span className="search-prompt">></span>
          <input
            type="text"
            placeholder="ENTER DOMAIN TO INVESTIGATE..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>
        <button type="submit" disabled={loading}>
          {loading ? 'ANALYZING...' : '[INVESTIGATE]'}
        </button>
      </form>

      {investigation && (
        <div className="investigation-results">
          <div className="investigation-header">
            <h3>{investigation.domain}</h3>
            <div className="risk-badge" style={{ 
              backgroundColor: investigation.risk_score > 0.7 ? '#ef4444' : 
                             investigation.risk_score > 0.4 ? '#f97316' : '#22c55e'
            }}>
              RISK: {(investigation.risk_score * 100).toFixed(0)}%
            </div>
          </div>

          <div className="investigation-grid">
            <div className="investigation-card">
              <h4>> NLP ANALYSIS</h4>
              <p>{investigation.nlp_explanation}</p>
            </div>

            <div className="investigation-card">
              <h4>> DOM INDICATORS</h4>
              <ul>
                {investigation.dom_indicators.map((indicator, i) => (
                  <li key={i}>{indicator}</li>
                ))}
              </ul>
            </div>

            <div className="investigation-card">
              <h4>> INFRASTRUCTURE (GNN)</h4>
              <div className="infra-score">
                <span>GNN SCORE:</span>
                <span className="score">{(investigation.infra_gnn_score * 100).toFixed(0)}%</span>
              </div>
              <div className="campaign-info">
                <span>CAMPAIGN:</span>
                <span className="campaign-id">{investigation.campaign_id || 'NONE'}</span>
              </div>
            </div>

            <div className="investigation-card">
              <h4>> DOMAIN INFO</h4>
              <div className="info-row">
                <span>AGE:</span>
                <span>{investigation.domain_age_days} DAYS</span>
              </div>
              <div className="info-row">
                <span>REGISTRAR:</span>
                <span>{investigation.whois_summary?.registrar}</span>
              </div>
              <div className="info-row">
                <span>CREATED:</span>
                <span>{investigation.whois_summary?.created_date}</span>
              </div>
            </div>

            <div className="investigation-card wide">
              <h4>> RELATED DOMAINS</h4>
              <table>
                <thead>
                  <tr>
                    <th>> DOMAIN</th>
                    <th>> RELATION</th>
                    <th>> RISK</th>
                  </tr>
                </thead>
                <tbody>
                  {investigation.related_domains?.map((rel, i) => (
                    <tr key={i}>
                      <td>{rel.domain}</td>
                      <td>{rel.relation}</td>
                      <td>{(rel.risk * 100).toFixed(0)}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ============== MAIN APP ==============

function App() {
  const [token, setToken] = useState(localStorage.getItem('phishguard_token'));
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('phishguard_user');
    return stored ? JSON.parse(stored) : null;
  });
  const [activeView, setActiveView] = useState('overview');

  const handleLogin = (newToken, newUser) => {
    localStorage.setItem('phishguard_token', newToken);
    localStorage.setItem('phishguard_user', JSON.stringify(newUser));
    setToken(newToken);
    setUser(newUser);
  };

  const handleLogout = () => {
    localStorage.removeItem('phishguard_token');
    localStorage.removeItem('phishguard_user');
    setToken(null);
    setUser(null);
  };

  if (!token || !user) {
    return <Login onLogin={handleLogin} />;
  }

  const renderView = () => {
    switch (activeView) {
      case 'overview':
        return <OverviewDashboard token={token} />;
      case 'live-threats':
        return <LiveThreats token={token} />;
      case 'campaigns':
        return <CampaignsView token={token} />;
      case 'graph':
        return <InfrastructureGraph token={token} />;
      case 'endpoints':
        return <EndpointsView token={token} />;
      case 'trends':
        return <TrendsView token={token} />;
      case 'investigate':
        return <InvestigateView token={token} />;
      default:
        return <OverviewDashboard token={token} />;
    }
  };

  return (
    <div className="app">
      <Sidebar 
        activeView={activeView} 
        setActiveView={setActiveView} 
        user={user}
        onLogout={handleLogout}
      />
      <main className="main-content">
        <header className="main-header">
          <h1>> {activeView.toUpperCase().replace('-', ' ')}</h1>
          <div className="header-actions">
            <span className="status-indicator">
              <span className="status-dot"></span>
              SYSTEM ONLINE
            </span>
          </div>
        </header>
        <div className="content">
          {renderView()}
        </div>
      </main>
    </div>
  );
}

export default App;
