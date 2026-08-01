import { Routes } from '@angular/router';
import { MsalGuard } from '@azure/msal-angular';
import { BacklogPage } from './backlog/backlog';
import { HomePage } from './home/home';
import { PbiDetailPage } from './pbi-detail/pbi-detail';

export const routes: Routes = [
  // 未認証ユーザーは MsalGuard に弾かれ、サインインへリダイレクトされる
  // （提案書 B-03「未認証ユーザーはルートガードで弾かれる」）。
  // 認証・所属の入口（B-03/B-10）。
  { path: '', component: HomePage, canActivate: [MsalGuard] },
  // プロダクトバックログ画面（画面A。B-17）。2画面構成の1枚目（D-21）。
  { path: 'backlog', component: BacklogPage, canActivate: [MsalGuard] },
  // PBI 詳細（B-18）。画面Aからのドリルダウンで、新しいモードではない（2画面原則を維持）。
  { path: 'backlog/:pbiId', component: PbiDetailPage, canActivate: [MsalGuard] },
];
