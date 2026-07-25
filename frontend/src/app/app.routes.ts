import { Routes } from '@angular/router';
import { MsalGuard } from '@azure/msal-angular';
import { HomePage } from './home/home';

export const routes: Routes = [
  // 唯一のページ。未認証ユーザーは MsalGuard に弾かれ、サインインへリダイレクトされる
  // （提案書 B-03「未認証ユーザーはルートガードで弾かれる」）。
  { path: '', component: HomePage, canActivate: [MsalGuard] },
];
