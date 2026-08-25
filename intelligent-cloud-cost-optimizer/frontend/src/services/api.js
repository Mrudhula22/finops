import axios from 'axios';

const API = axios.create({ baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000' });

// Attach token
API.interceptors.request.use(cfg => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// Auto-logout on 401
API.interceptors.response.use(r => r, err => {
  if (err.response?.status === 401) {
    localStorage.removeItem('token');
    window.location.href = '/login';
  }
  return Promise.reject(err);
});

export const auth = {
  login:    d => API.post('/api/auth/login', d).then(r => r.data),
  register: d => API.post('/api/auth/register', d).then(r => r.data),
  me:       ()=> API.get('/api/auth/me').then(r => r.data),
};

export const dashboard = {
  summary:  ()=> API.get('/api/dashboard/summary').then(r => r.data),
  query:    d => API.post('/api/dashboard/query', d).then(r => r.data),
};

export const costs = {
  summary:   ()        => API.get('/api/costs/summary').then(r => r.data),
  breakdown: (p)       => API.get('/api/costs/breakdown', { params: { provider: p } }).then(r => r.data),
  history:   (months)  => API.get('/api/costs/history', { params: { months } }).then(r => r.data),
  anomalies: ()        => API.get('/api/costs/anomalies').then(r => r.data),
  resources: (p)       => API.get('/api/costs/resources', { params: { provider: p } }).then(r => r.data),
};

export const forecast = {
  predict:   d  => API.post('/api/forecast/predict', d).then(r => r.data),
  compare:   p  => API.get('/api/forecast/compare', { params: { provider: p } }).then(r => r.data),
  budgetRisk:()  => API.get('/api/forecast/budget-risk').then(r => r.data),
  experiments:(p)=> API.post('/api/forecast/experiments', null, { params: { provider: p } }).then(r => r.data),
};

export const recommendations = {
  list:    (params) => API.get('/api/recommendations/', { params }).then(r => r.data),
  get:     (id)     => API.get(`/api/recommendations/${id}`).then(r => r.data),
  generate:(d)      => API.post('/api/recommendations/generate', d).then(r => r.data),
  approve: (id, d)  => API.post(`/api/recommendations/${id}/approve`, d).then(r => r.data),
  execute: (id)     => API.post(`/api/recommendations/${id}/execute`).then(r => r.data),
  savings: ()       => API.get('/api/recommendations/savings').then(r => r.data),
  whatif:  (d)      => API.post('/api/recommendations/whatif/simulate', d).then(r => r.data),
};

export const multicloud = {
  compare:    (params) => API.get('/api/multicloud/compare', { params }).then(r => r.data),
  compareAll: ()       => API.get('/api/multicloud/compare/all').then(r => r.data),
  security:   ()       => API.get('/api/multicloud/security').then(r => r.data),
  pricing:    (t)      => API.get('/api/multicloud/pricing', { params: { resource_type: t } }).then(r => r.data),
};

export const execution = {
  history: (params) => API.get('/api/execution/history', { params }).then(r => r.data),
  pending: ()       => API.get('/api/execution/pending').then(r => r.data),
  rollback:(id, r)  => API.post(`/api/execution/rollback/${id}`, null, { params: { reason: r } }).then(r => r.data),
};

export default API;
