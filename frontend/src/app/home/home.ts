import { HttpClient } from '@angular/common/http';
import { Component, OnInit, inject, signal } from '@angular/core';

interface HealthResponse {
  status: string;
  service: string;
}

@Component({
  selector: 'app-home',
  templateUrl: './home.html',
  styleUrl: './home.scss',
})
export class HomePage implements OnInit {
  private readonly http = inject(HttpClient);

  protected readonly apiStatus = signal<string>('確認中…');

  ngOnInit(): void {
    this.http.get<HealthResponse>('/api/health').subscribe({
      next: (res) => this.apiStatus.set(`${res.status} (${res.service})`),
      error: () => this.apiStatus.set('未接続'),
    });
  }
}
