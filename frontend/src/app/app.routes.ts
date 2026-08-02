import { Routes } from '@angular/router';
import { MsalGuard } from '@azure/msal-angular';
import { BacklogPage } from './backlog/backlog';
import { HomePage } from './home/home';
import { PbiDetailPage } from './pbi-detail/pbi-detail';
import { environment } from '../environments/environment';

// E2E ビルドでは MSAL を配線しないためガードを外す（EX-1・D-22）。認証は
// バックエンドの env ゲート resolver に委ねる。本番／通常ビルドでは environment.e2e が
// 静的に false なので、常に [MsalGuard] が付く。
const authGuard = environment.e2e ? [] : [MsalGuard];

export const routes: Routes = [
  // 未認証ユーザーは MsalGuard に弾かれ、サインインへリダイレクトされる
  // （提案書 B-03「未認証ユーザーはルートガードで弾かれる」）。
  // 認証・所属の入口（B-03/B-10）。
  { path: '', component: HomePage, canActivate: authGuard },
  // プロダクトバックログ画面（画面A。B-17）。2画面構成の1枚目（D-21）。
  { path: 'backlog', component: BacklogPage, canActivate: authGuard },
  // PBI 詳細（B-18）。画面Aからのドリルダウンで、新しいモードではない（2画面原則を維持）。
  { path: 'backlog/:pbiId', component: PbiDetailPage, canActivate: authGuard },
];
