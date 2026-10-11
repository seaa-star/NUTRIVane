import axios from "axios";
import { getAccessToken } from "@/lib/supabase";

const BASE = process.env.REACT_APP_BACKEND_URL;
export const api = axios.create({ baseURL: `${BASE}/api` });

api.interceptors.request.use(async (config) => {
  const token = await getAccessToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const getHome = () => api.get("/home").then((r) => r.data);
export const getRecipes = (params) => api.get("/recipes", { params }).then((r) => r.data);
export const getRecipe = (slug) => api.get(`/recipes/${slug}`).then((r) => r.data);
export const getCategories = () => api.get("/categories").then((r) => r.data);
export const getMoods = () => api.get("/moods").then((r) => r.data);
export const getMood = (key) => api.get(`/moods/${key}`).then((r) => r.data);
export const postMoodRecommend = (body) => api.post("/mood/recommend", body).then((r) => r.data);
export const getMoodWeekly = () => api.get("/mood/weekly").then((r) => r.data);
export const getMoodHistory = () => api.get("/mood/history").then((r) => r.data);
export const getMoodLog = (id) => api.get(`/mood/history/${id}`).then((r) => r.data);
export const addAiFavorite = (body) => api.post("/ai-favorites", body).then((r) => r.data);
export const removeAiFavorite = (id) => api.delete(`/ai-favorites/${id}`).then((r) => r.data);
export const updateCountries = (body) => api.put("/me/countries", body).then((r) => r.data);
export const getInsight = (slug) => api.get(`/insight/${slug}`).then((r) => r.data);
export const postScan = (body) => api.post("/scan", body).then((r) => r.data);
export const postScanAi = (body) => api.post("/scan/ai", body).then((r) => r.data);
export const getMe = () => api.get("/me").then((r) => r.data);
export const getFavorites = () => api.get("/favorites").then((r) => r.data);
export const addFavorite = (slug) => api.put(`/favorites/${slug}`).then((r) => r.data);
export const removeFavorite = (slug) => api.delete(`/favorites/${slug}`).then((r) => r.data);
