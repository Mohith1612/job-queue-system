import axios, { AxiosError } from 'axios'

export class RateLimitError extends Error {
  constructor() {
    super('Rate limit exceeded — please wait before submitting more jobs')
    this.name = 'RateLimitError'
  }
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '',
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 429) {
      return Promise.reject(new RateLimitError())
    }
    return Promise.reject(error)
  }
)

export default client
