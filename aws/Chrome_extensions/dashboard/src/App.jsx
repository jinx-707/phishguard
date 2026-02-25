/**
 * PhishGuard Enterprise SOC Dashboard
 * React Frontend - Main Dashboard Application
 */

import React, { useState, useEffect, useCallback } from 'react';
import { LineChart, Line, BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import './dashboard.css';

// API Base URL - uses relative path for proxy support
const API_BASE = '/api/v1';

// Colors
const COLORS = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#3b82f6', '#8b5cf6'];

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
      <div className="login-box">
        <h1>🛡️ PhishGuard SOC</h1>
        <p>Enterprise Threat Intelligence</p>
        
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          {error && <div className="error">{error}</div>}
          <button type="submit" disabled={loading}>
            {loading ? 'Signing in...' : 'Sign In'}
          </button>
        </form>
        
        <div className="demo-credentials">
          <p>Demo: admin / admin123</p>
        </div>
      </div>
    </div>
  );
}

// ============== SIDEBAR ==============

function Sidebar({ activeView, setActiveView, user, onLogout }) {
  const menuItems = [
    { id: 'overview', icon: '📊', label: 'Overview' },
    { id: 'live-threats', icon: '⚡', label: 'Live Threats' },
    { id: 'campaigns', icon: '🎯', label: 'Campaigns' },
    { id: 'graph', icon: '🔗', label: 'Infrastructure' },
    { id: 'endpoints', icon: '💻', label: 'Endpoints' },
    { id: 'trends', icon: '📈', label: 'Trends' },
    { id: 'investigate', icon: '🔍', label: 'Investigate' },
    { id: 'admin', icon: '⚙️', label: 'Admin' },
  ];

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>🛡️ PhishGuard</h2>
        <span className="badge">SOC</span>
      </div>
      
      <nav className="sidebar-nav">
        {menuItems.map(item => (
          <button
            key={item.id}
            className={`nav-item ${activeView === item.id ? 'active' : ''}`}
            onClick={() => setActiveView(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        ))}
      </nav>
      
      <div className="sidebar-footer">
        <div className="user-info">
          <span className="user-name">{user?.full_name || 'User'}</span>
          <span className="user-role">{user?.role || 'viewer'}</span>
        </div>
        <button className="logout-btn" onClick={onLogout}>Logout</button>
      </div>
    </aside>
  );
}

// ============== OVERVIEW DASHBOARD ==============

function OverviewDashboard({ token }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(`${API_BASE}/dashboard/summary`, {
      headers: { 'Authorization': `Bearer ${token}` }
    })
      .then(res => res.json())
      .then(data => setSummary(data))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <div className="loading">Loading dashboard...</div>;

  return (
    <div className="dashboard-grid">
      <div className="stat-card primary">
        <h3>Threats Blocked Today</h3>
        <div className="stat-value">{summary?.total_threats_blocked_today || 0}</div>
        <div className="stat-trend positive">↑ 12% from yesterday</div>
      </div>
      
      <div className="stat-card warning">
        <h3>Active Campaigns</h3>
        <div className="stat-value">{summary?.active_campaigns || 0}</div>
        <div className="stat-trend">Requires attention</div>
      </div>
      
      <div className="stat-card danger">
        <h3>Zero-Day Detections</h3>
        <div className="stat-value">{summary?.zero_day_detections || 0}</div>
        <div className="stat-trend negative">↑ 3 new today</div>
      </div>
      
      <div className="stat-card info">
        <h3>Endpoints Protected</h3>
        <div className="stat-value">{summary?.endpoints_protected?.toLocaleString() || 0}</div>
        <div className="stat-trend positive">↑ 24 this hour</div>
      </div>

      <div className="card wide">
        <h3>🎯 Top Targeted Brands</h3>
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
              <span className="brand-count">{brand.attempts}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="card wide">
        <h3>📋 Recent Activity</h3>
        <div className="activity-list">
          {summary?.recent_activity?.map((activity, i) => (
            <div key={i} className={`activity-item ${activity.severity}`}>
              <span className="activity-time">{activity.time}</span>
              <span className="activity-event">{activity.event}</span>
              <span className={`severity-badge ${activity.severity}`}>{activity.severity}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ============== LIVE THREATS ==============

function LiveThreats({ token }) {
  const [threats, setThreats] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchThreats = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/dashboard/live-threats?limit=20`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const data = await res.json();
      setThreats(data);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchThreats();
    const interval = setInterval(fetchThreats, 5000);
    return () => clearInterval(interval);
  }, [fetchThreats]);

  const getSourceColor = (source) => {
    const colors = { 'GNN': '#8b5cf6', 'NLP': '#3b82f6', 'DOM': '#f97316', 'INFRA': '#22c55e' };
    return colors[source] || '#6b7280';
  };

  if (loading) return <div className="loading">Loading threats...</div>;

  return (
    <div className="live-threats">
      <div className="section-header">
        <h2>⚡ Live Threat Feed</h2>
        <span className="live-indicator">● Live</span>
      </div>
      
      <div className="threats-table">
        <table>
          <thead>
            <tr>
              <th>Domain</th>
              <th>Risk Score</th>
              <th>Confidence</th>
              <th>Source</th>
              <th>Campaign</th>
              <th>Time</th>
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
                <td>{threat.campaign_id || '-'}</td>
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

  if (loading) return <div className="loading">Loading campaigns...</div>;

  return (
    <div className="campaigns-view">
      <h2>🎯 Campaign Intelligence</h2>
      
      <div className="campaigns-grid">
        {campaigns.map(campaign => (
          <div key={campaign.campaign_id} className="campaign-card">
            <div className="campaign-header">
              <h3>{campaign.campaign_id}</h3>
              <span className={`trend-badge ${campaign.growth_trend}`}>
                {campaign.growth_trend === 'growing' ? '📈' : '➡️'}
              </span>
            </div>
            
            <div className="campaign-stats">
              <div className="campaign-stat">
                <span className="stat-label">Cluster Size</span>
                <span className="stat-value">{campaign.cluster_size} domains</span>
              </div>
              <div className="campaign-stat">
                <span className="stat-label">Avg Risk</span>
                <span className="stat-value">{(campaign.avg_risk_score * 100).toFixed(0)}%</span>
              </div>
            </div>
            
            <div className="campaign-infra">
              <h4>Shared Infrastructure</h4>
              <div className="infra-item">
                <span className="infra-label">IP:</span>
                <span className="infra-value">{campaign.shared_ip}</span>
              </div>
              <div className="infra-item">
                <span className="infra-label">Cert:</span>
                <span className="infra-value">{campaign.shared_cert}</span>
              </div>
            </div>
            
            <div className="campaign-domains">
              <h4>Domains ({campaign.domains.length})</h4>
              <ul>
                {campaign.domains.slice(0, 3).map((domain, i) => (
                  <li key={i}>{domain}</li>
                ))}
                {campaign.domains.length > 3 && (
                  <li className="more">+{campaign.domains.length - 3} more</li>
                )}
              </ul>
            </div>
            
            <div className="campaign-footer">
              <span className="first-seen">First seen: {new Date(campaign.first_seen).toLocaleDateString()}</span>
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

  if (loading) return <div className="loading">Loading graph...</div>;

  // Simple force-directed layout
  const nodes = graphData?.nodes?.map((node, i) => ({
    ...node,
    x: 100 + (i % 4) * 200,
    y: 100 + Math.floor(i / 4) * 150
  })) || [];

  return (
    <div className="graph-view">
      <h2>🔗 Infrastructure Graph</h2>
      
      <div className="graph-container">
        <svg viewBox="0 0 800 600" className="graph-svg">
          {/* Edges */}
          {graphData?.edges?.map((edge, i) => {
            const source = nodes.find(n => n.id === edge.source);
            const target = nodes.find(n => n.id === edge.target);
            if (!source || !target) return null;
            return (
              <line
                key={i}
                x1={source.x} y1={source.y}
                x2={target.x} y2={target.y}
                stroke="#64748b"
                strokeWidth="2"
                strokeOpacity="0.5"
              />
            );
          })}
          
          {/* Nodes */}
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
                stroke="#fff"
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
          <h3>Node Details</h3>
          <div className="detail-row">
            <span className="label">ID:</span>
            <span className="value">{selectedNode.id}</span>
          </div>
          <div className="detail-row">
            <span className="label">Label:</span>
            <span className="value">{selectedNode.label}</span>
          </div>
          <div className="detail-row">
            <span className="label">Type:</span>
            <span className="value">{selectedNode.type}</span>
          </div>
          <div className="detail-row">
            <span className="label">Risk:</span>
            <span className="value">{(selectedNode.risk * 100).toFixed(0)}%</span>
          </div>
          <button onClick={() => setSelectedNode(null)}>Close</button>
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

  if (loading) return <div className="loading">Loading endpoint stats...</div>;

  return (
    <div className="endpoints-view">
      <h2>💻 Endpoint Statistics</h2>
      
      <div className="endpoint-grid">
        <div className="endpoint-stat">
          <div className="stat-icon">🖥️</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.total_endpoints?.toLocaleString()}</span>
            <span className="stat-label">Total Endpoints</span>
          </div>
        </div>
        
        <div className="endpoint-stat">
          <div className="stat-icon">⚡</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.scans_per_minute}</span>
            <span className="stat-label">Scans/Minute</span>
          </div>
        </div>
        
        <div className="endpoint-stat danger">
          <div className="stat-icon">🚫</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.blocked_attempts?.toLocaleString()}</span>
            <span className="stat-label">Blocked Attempts</span>
          </div>
        </div>
        
        <div className="endpoint-stat warning">
          <div className="stat-icon">⚠️</div>
          <div className="stat-info">
            <span className="stat-value">{(stats?.override_rate * 100).toFixed(1)}%</span>
            <span className="stat-label">Override Rate</span>
          </div>
        </div>
        
        <div className="endpoint-stat info">
          <div className="stat-icon">📴</div>
          <div className="stat-info">
            <span className="stat-value">{stats?.offline_detections}</span>
            <span className="stat-label">Offline Detections</span>
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

  if (loading) return <div className="loading">Loading trends...</div>;

  return (
    <div className="trends-view">
      <h2>📈 Risk Trend Analytics</h2>
      
      <div className="charts-grid">
        <div className="chart-card">
          <h3>Daily Blocked Attempts</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{fontSize: 12}} />
              <YAxis />
              <Tooltip />
              <Line type="monotone" dataKey="blocked_count" stroke="#ef4444" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>
        
        <div className="chart-card">
          <h3>Zero-Day Detections</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={trends}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="date" tick={{fontSize: 12}} />
              <YAxis />
              <Tooltip />
              <Bar dataKey="zero_day_count" fill="#f97316" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        
        <div className="chart-card">
          <h3>Campaign Distribution</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={trends}
                dataKey="new_campaigns"
                nameKey="date"
                cx="50%"
                cy="50%"
                outerRadius={80}
              >
                {trends.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
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
      <h2>🔍 Alert Investigation</h2>
      
      <form className="search-form" onSubmit={handleSearch}>
        <input
          type="text"
          placeholder="Enter domain to investigate..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Investigating...' : 'Investigate'}
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
              Risk: {(investigation.risk_score * 100).toFixed(0)}%
            </div>
          </div>

          <div className="investigation-grid">
            <div className="investigation-card">
              <h4>🧠 NLP Analysis</h4>
              <p>{investigation.nlp_explanation}</p>
            </div>

            <div className="investigation-card">
              <h4>🌐 DOM Indicators</h4>
              <ul>
                {investigation.dom_indicators.map((indicator, i) => (
                  <li key={i}>{indicator}</li>
                ))}
              </ul>
            </div>

            <div className="investigation-card">
              <h4>🔗 Infrastructure (GNN)</h4>
              <div className="infra-score">
                <span>GNN Score:</span>
                <span className="score">{(investigation.infra_gnn_score * 100).toFixed(0)}%</span>
              </div>
              <div className="campaign-info">
                <span>Campaign:</span>
                <span className="campaign-id">{investigation.campaign_id || 'None'}</span>
              </div>
            </div>

            <div className="investigation-card">
              <h4>📅 Domain Info</h4>
              <div className="info-row">
                <span>Age:</span>
                <span>{investigation.domain_age_days} days</span>
              </div>
              <div className="info-row">
                <span>Registrar:</span>
                <span>{investigation.whois_summary?.registrar}</span>
              </div>
              <div className="info-row">
                <span>Created:</span>
                <span>{investigation.whois_summary?.created_date}</span>
              </div>
            </div>

            <div className="investigation-card wide">
              <h4>🔗 Related Domains</h4>
              <table>
                <thead>
                  <tr>
                    <th>Domain</th>
                    <th>Relation</th>
                    <th>Risk</th>
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

// ============== ADMIN VIEW - Enterprise Overrides & Policy ==============

function AdminView({ token }) {
  const [policyMode, setPolicyMode] = useState('BALANCED');
  const [overrides, setOverrides] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newOverride, setNewOverride] = useState({ domain: '', action: 'BLOCK', reason: '' });
  const [saving, setSaving] = useState(false);

  // Fetch policy mode and overrides
  useEffect(() => {
    const fetchData = async () => {
      try {
        const [policyRes, overridesRes] = await Promise.all([
          fetch(`${API_BASE}/admin/policy-mode`, { headers: { 'Authorization': `Bearer ${token}` } }),
          fetch(`${API_BASE}/admin/overrides`, { headers: { 'Authorization': `Bearer ${token}` } })
        ]);
        
        const policyData = await policyRes.json();
        const overridesData = await overridesRes.json();
        
        setPolicyMode(policyData.policy_mode || 'BALANCED');
        setOverrides(overridesData || []);
      } catch (err) {
        console.error('Failed to fetch admin data:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
  }, [token]);

  // Update policy mode
  const handlePolicyChange = async (newMode) => {
    setSaving(true);
    try {
      await fetch(`${API_BASE}/admin/policy-mode`, {
        method: 'PUT',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ policy_mode: newMode })
      });
      setPolicyMode(newMode);
    } catch (err) {
      console.error('Failed to update policy:', err);
    } finally {
      setSaving(false);
    }
  };

  // Create override
  const handleCreateOverride = async (e) => {
    e.preventDefault();
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/admin/overrides`, {
        method: 'POST',
        headers: { 
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(newOverride)
      });
      
      if (res.ok) {
        // Refresh overrides list
        const overridesRes = await fetch(`${API_BASE}/admin/overrides`, { 
          headers: { 'Authorization': `Bearer ${token}` } 
        });
        const overridesData = await overridesRes.json();
        setOverrides(overridesData || []);
        setShowCreateForm(false);
        setNewOverride({ domain: '', action: 'BLOCK', reason: '' });
      } else {
        const error = await res.json();
        alert(error.detail || 'Failed to create override');
      }
    } catch (err) {
      console.error('Failed to create override:', err);
    } finally {
      setSaving(false);
    }
  };

  // Delete override
  const handleDeleteOverride = async (id) => {
    if (!confirm('Are you sure you want to delete this override?')) return;
    
    setSaving(true);
    try {
      await fetch(`${API_BASE}/admin/overrides/${id}`, {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });
      
      // Refresh list
      const overridesRes = await fetch(`${API_BASE}/admin/overrides`, { 
        headers: { 'Authorization': `Bearer ${token}` } 
      });
      const overridesData = await overridesRes.json();
      setOverrides(overridesData || []);
    } catch (err) {
      console.error('Failed to delete override:', err);
    } finally {
      setSaving(false);
    }
  };

  const getActionBadge = (action) => {
    return action === 'ALLOW' 
      ? <span className="action-badge allow">ALLOW</span>
      : <span className="action-badge block">BLOCK</span>;
  };

  if (loading) return <div className="loading">Loading admin panel...</div>;

  return (
    <div className="admin-view">
      <h2>⚙️ Admin - Enterprise Policy</h2>
      
      {/* Policy Mode Section */}
      <div className="admin-section">
        <h3>🛡️ Policy Mode</h3>
        <p className="section-description">
          Select how detection results are translated into blocking decisions.
        </p>
        
        <div className="policy-modes">
          <button 
            className={`policy-btn ${policyMode === 'STRICT' ? 'active strict' : ''}`}
            onClick={() => handlePolicyChange('STRICT')}
            disabled={saving}
          >
            <span className="policy-icon">🔒</span>
            <span className="policy-name">STRICT</span>
            <span className="policy-desc">Block HIGH + MEDIUM</span>
          </button>
          
          <button 
            className={`policy-btn ${policyMode === 'BALANCED' ? 'active balanced' : ''}`}
            onClick={() => handlePolicyChange('BALANCED')}
            disabled={saving}
          >
            <span className="policy-icon">⚖️</span>
            <span className="policy-name">BALANCED</span>
            <span className="policy-desc">Block HIGH, Warn MEDIUM</span>
          </button>
          
          <button 
            className={`policy-btn ${policyMode === 'PERMISSIVE' ? 'active permissive' : ''}`}
            onClick={() => handlePolicyChange('PERMISSIVE')}
            disabled={saving}
          >
            <span className="policy-icon">🔓</span>
            <span className="policy-name">PERMISSIVE</span>
            <span className="policy-desc">Block known only</span>
          </button>
        </div>
        
        <div className="current-policy">
          Current Policy: <strong>{policyMode}</strong>
        </div>
      </div>

      {/* Overrides Section */}
      <div className="admin-section">
        <div className="section-header">
          <h3>🚫 Enterprise Overrides</h3>
          <button 
            className="btn-primary"
            onClick={() => setShowCreateForm(!showCreateForm)}
          >
            {showCreateForm ? 'Cancel' : '+ Add Override'}
          </button>
        </div>
        
        <p className="section-description">
          Explicitly allow or block specific domains, overriding detection.
        </p>

        {/* Create Form */}
        {showCreateForm && (
          <form className="override-form" onSubmit={handleCreateOverride}>
            <div className="form-row">
              <input
                type="text"
                placeholder="domain.com"
                value={newOverride.domain}
                onChange={(e) => setNewOverride({...newOverride, domain: e.target.value})}
                required
              />
              <select
                value={newOverride.action}
                onChange={(e) => setNewOverride({...newOverride, action: e.target.value})}
              >
                <option value="BLOCK">BLOCK</option>
                <option value="ALLOW">ALLOW</option>
              </select>
            </div>
            <div className="form-row">
              <input
                type="text"
                placeholder="Reason (optional)"
                value={newOverride.reason}
                onChange={(e) => setNewOverride({...newOverride, reason: e.target.value})}
              />
              <button type="submit" className="btn-primary" disabled={saving}>
                {saving ? 'Creating...' : 'Create Override'}
              </button>
            </div>
          </form>
        )}

        {/* Overrides Table */}
        <div className="overrides-table">
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                <th>Action</th>
                <th>Reason</th>
                <th>Created By</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {overrides.length === 0 ? (
                <tr>
                  <td colSpan="6" className="empty-message">No overrides configured</td>
                </tr>
              ) : (
                overrides.map(override => (
                  <tr key={override.id}>
                    <td className="domain-cell">{override.domain}</td>
                    <td>{getActionBadge(override.action)}</td>
                    <td className="reason-cell">{override.reason || '-'}</td>
                    <td>{override.created_by}</td>
                    <td>{new Date(override.created_at).toLocaleDateString()}</td>
                    <td>
                      <button 
                        className="btn-delete"
                        onClick={() => handleDeleteOverride(override.id)}
                        disabled={saving}
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

// ============== MAIN APP ==============

function App() {
  const [activeView, setActiveView] = useState('overview');
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  // Auto-login on startup
  useEffect(() => {
    const login = async () => {
      try {
        const formData = new URLSearchParams();
        formData.append('username', 'admin');
        formData.append('password', 'admin123');
        
        const response = await fetch(`${API_BASE}/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
          body: formData
        });
        
        if (response.ok) {
          const data = await response.json();
          setToken(data.access_token);
        }
      } catch (err) {
        console.error('Auto-login failed:', err);
      } finally {
        setLoading(false);
      }
    };
    
    login();
  }, []);

  // Default user (no login page)
  const user = { full_name: 'Security Admin', role: 'admin' };

  if (loading) {
    return <div className="loading">Loading PhishGuard...</div>;
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
      case 'admin':
        return <AdminView token={token} />;
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
      />
      <main className="main-content">
        <header className="main-header">
          <h1>{activeView.replace('-', ' ').toUpperCase()}</h1>
          <div className="header-actions">
            <span className="status-indicator">
              <span className="status-dot"></span>
              System Online
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

