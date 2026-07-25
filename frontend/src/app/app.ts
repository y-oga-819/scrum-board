import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterOutlet } from '@angular/router';

import { AuthService } from './auth/auth.service';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  templateUrl: './app.html',
  styleUrl: './app.scss',
})
export class App implements OnInit {
  private readonly auth = inject(AuthService);

  protected readonly title = signal('Scrum Board');

  ngOnInit(): void {
    // サインインのリダイレクトから戻ってきた応答をここで1度だけ処理する。
    this.auth.handleRedirect();
  }
}
