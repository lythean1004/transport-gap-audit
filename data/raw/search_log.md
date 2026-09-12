# 공식 원문 후보 검색 실행 기록

- 실행일: 2026-08-26 (Asia/Seoul)
- 원칙: 아래 순서대로 실제 검색하고, 검색결과·목록 페이지는 최종 후보 URL에서 제외했다.
- 검증: 최종 후보에 사용한 직접 문서 URL은 `url_verification.csv`에서 HTTP 200과 본문 바이트 수를 기록했다.
- 참고: 여러 지명을 쉼표로 한꺼번에 넣은 검색은 결과 잡음이 많아, 같은 검색군 안에서 지구별 공식 도메인 보완검색을 추가했다.

## 1. 과거 검증 5곳

|순서|실행 검색어|대표 공식 결과 및 판정|
|---:|---|---|
|1|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 입주 시작"`|[동탄2 첫 입주(LH)](https://www.lh.or.kr/gallery.es?act=view&b_list=8&bid=0003&keyField=&list_no=7977&mid=a10502000000&nPage=342&orderby=&vlist_no_npage=547), [미사 첫 입주(LH)](https://www.lh.or.kr/gallery.es?act=view&b_list=8&bid=0003&keyField=&list_no=7400&mid=a10502000000&nPage=420&orderby=&vlist_no_npage=672). 통합검색 결과가 일부 지구에 편중됨.|
|2|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 입주개시일 LH"`|[김포한강 첫 입주(국토부)](https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95068404&lcmspage=346), [위례 최초입주 회고(서울시)](https://mediahub.seoul.go.kr/archives/2015024). LH 키워드가 있어도 타 공식기관 문서가 함께 노출됨.|
|3|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 입주자 사전점검"`|사전점검 자체 문서보다 블록별 모집공고가 다수 노출. [하남미사 블록 입주예정월(LH)](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=08&ccrCnntSysDsCd=02&mi=1026&panId=0000060513&uppAisTpCd=06)을 후보 발견용으로 사용.|
|4|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 광역교통개선대책 국토교통부"`|[동탄2 특별대책(대광위)](https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?id=95087345&lcmspage=5), [하남 미사 광역교통대책 회고(하남시)](https://www.hanam.go.kr/sosik/selectBbsNttView.do?bbsNo=1164&integrDeptCode=&key=10048&nttNo=221988&pageIndex=392&searchCnd=all&searchCtgry=&searchKrwd=&selectPageUnit=).|
|5|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 광역교통개선대책 국토교통부" site:molit.go.kr`|[동탄2 특별대책 주민간담회](https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?id=95086846&lcmspage=1), [동탄2 초기 개발계획](https://www.molit.go.kr/USR/NEWS/m_18578/dtl.jsp?id=155208949&lcmspage=157).|
|6|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 광역교통개선대책 국토교통부" site:lh.or.kr`|[김포한강 행복주택 교통망도 PDF](https://lh.or.kr/boardDownload.es?bid=0034&list_no=646666&seq=3), [김포양곡 교통망도 PDF](https://lh.or.kr/boardDownload.es?bid=0034&list_no=646642&seq=3).|
|7|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 교통대책 보도자료" site:molit.go.kr`|[GTX-A 수서~동탄 개통](https://www.molit.go.kr/USR/NEWS/m_72/dtl.jsp?id=95089607&lcmspage=2), [별내선 개통](https://molit.go.kr/atmo/USR/N0201/m_36515/dtl.jsp?id=95090058&lcmspage=77).|
|8|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 교통대책 보도자료" site:lh.or.kr`|LH 보도자료보다 공급공고·홍보 PDF가 우세. 약속일 후보는 김포한강 교통망도 2건으로 좁힘.|
|9|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 버스 노선 개통"`|[위례 똑버스 운행(하남시)](https://www.hanam.go.kr/cleanh/cleanhBbsNttWebView.do?key=4348&nttNo=2245), [하남선 1단계 운행 회고](https://www.hanam.go.kr/sosik/selectBbsNttView.do?bbsNo=1164&integrDeptCode=&key=10048&nttNo=221988&pageIndex=392&searchCnd=all&searchCtgry=&searchKrwd=&selectPageUnit=).|
|10|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 광역버스 운행 개시 공지"`|[김포골드라인 첫 열차(김포시)](https://gimpo.go.kr/news/selectBbsNttView.do?bbsNo=466&key=9377&nttNo=94282&pageIndex=124&pageUnit=10&searchCnd=all&searchKrwd=%EC%96%B4%EB%A6%B0%EC%9D%B4), [SRT 첫 운행(SR)](https://www.srail.or.kr/cms/article/view.do?pageId=KR0502000000&postNo=56). 버스만으로는 지구별 2건이 채워지지 않아 운영기관 철도 공지를 병행.|
|11|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 버스 노선 개통" site:go.kr`|[별내선 첫 열차(경기도)](https://gnews.gg.go.kr/briefing/brief_gongbo_view.do?BS_CODE=s017&number=62697&subject_Code=BO01), [위례 남위례역 개통(서울시)](https://mediahub.seoul.go.kr/archives/2003528).|
|12|`"화성 동탄2, 김포 한강, 위례, 남양주 다산, 하남 미사 광역버스 운행 개시" site:go.kr`|[다산 입주지원 특별대책반(경기도)](https://gnews.gg.go.kr/briefing/brief_gongbo_view.do?BS_CODE=S017&number=36361), [하남선 전 구간 첫 열차(하남시)](https://www.hanam.go.kr/sosik/selectBbsNttView.do?bbsNo=1164&integrDeptCode=&key=10048&nttNo=321801&pageIndex=258&searchCnd=all&searchCtgry=&searchKrwd=&selectPageUnit=).|

## 2. 추가 전방 모니터링 5곳

|순서|실행 검색어|대표 공식 결과 및 판정|
|---:|---|---|
|1|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장} 입주 시작"`|닫는 중괄호를 포함해 그대로 실행. 잡음이 많아 [3기 신도시 최초 본청약(LH)](https://www.lh.or.kr/gallery.es?act=view&b_list=8&bid=0003&list_no=11581&mid=a10502000000&nPage=1&vlist_no_npage=2)를 출발점으로 사용.|
|2|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 입주개시일 LH"`|[인천계양 A2](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=05&ccrCnntSysDsCd=02&mi=1027&panId=0000060752&uppAisTpCd=05), [남양주왕숙 A1](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=05&ccrCnntSysDsCd=02&mi=1027&panId=0000060926&uppAisTpCd=05), [하남교산 A2](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=05&ccrCnntSysDsCd=02&mi=1027&panId=0000060838&uppAisTpCd=05).|
|3|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 입주자 사전점검"`|사전점검 공지가 아직 없는 지구가 많아 본청약 직접 본문으로 보완. [고양창릉 A4](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=39&ccrCnntSysDsCd=02&mi=1027&panId=0000060802&uppAisTpCd=39), [부천대장 A5·A6](https://apply.lh.or.kr/lhapply/apply/wt/wrtanc/selectWrtancInfo.do?aisTpCd=42&ccrCnntSysDsCd=03&panId=2015122300020448&uppAisTpCd=39).|
|4|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장} 광역교통개선대책 국토교통부"`|닫는 중괄호를 포함해 그대로 실행. [왕숙·창릉 대책](https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?id=95084988&lcmspage=1), [교산 대책](https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?id=95083918&lcmspage=88).|
|5|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 광역교통개선대책 국토교통부" site:molit.go.kr`|[계양·대장 통합대책](https://www.molit.go.kr/mta/USR/N0201/m_36770/dtl.jsp?id=95085094&lcmspage=2), [2024 광역교통 투자계획 PDF](https://www.molit.go.kr/2024plan_traffic/news/bodo_2.pdf).|
|6|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 광역교통개선대책 국토교통부" site:lh.or.kr`|[고양창릉 본청약 보도자료(LH)](https://www.lh.or.kr/gallery.es?act=view&b_list=8&bid=0003&keyField=&list_no=11697&mid=a10502000000&nPage=1&orderby=&vlist_no_npage=1), LH ESG 자료가 보조 결과로 노출.|
|7|`"{인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장} 교통대책 보도자료" site:molit.go.kr`|중괄호를 포함해 그대로 실행. [계양·대장 S-BRT 시범사업 선정](https://molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95083361&lcmspage=57), [BRT 현황](https://www.molit.go.kr/mta/USR/WPGE0201/m_36794/DTL.jsp).|
|8|`"{인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장} 교통대책 보도자료" site:lh.or.kr`|LH의 공급·착공 자료가 주로 노출되어 교통 약속일은 국토부 확정 대책을 우선 채택.|
|9|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 버스 노선 개통"`|미입주 지구 내부의 실제 운행 개시는 대부분 미발생. [진접선 개통](https://www.molit.go.kr/USR/NEWS/m_71/dtl.jsp?id=95086587&lcmspage=60), [검단연장선 첫 운행](https://www.incheon.go.kr/IC010205/view?curPage=276&repSeq=DOM_0000000012563847)을 인접 `basic_service` 기준선으로 분리.|
|10|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장} 광역버스 운행 개시 공지"`|닫는 중괄호를 포함해 그대로 실행. 지구 내부 개통 공지 부재를 확인하고 미래 계획을 실제운행으로 기록하지 않음.|
|11|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 버스 노선 개통" site:go.kr`|[GTX-A 운정중앙~서울역 개통](https://www.molit.go.kr/USR/NEWS/dtl.jsp?id=95090469&lcmspage=47), [대곡~소사 개통](https://www.molit.go.kr/USR/NEWS/m_72/dtl.jsp?id=95088517&lcmspage=5). 모두 인접 기본서비스로만 분류.|
|12|`"인천 계양, 남양주 왕숙, 하남 교산, 고양 창릉, 부천 대장 광역버스 운행 개시" site:go.kr`|[부천시 소사~대곡선 현황](https://bucheon.go.kr/site/homepage/menu/viewMenu?menuid=148006006003003002), [인천1호선 검단연장 개통](https://www.incheon.go.kr/mayor_8/MA040101/view?curPage=195&repSeq=DOM_0000000012620245). 지구 약속 이행과 분리해 기록.|

## 보완 지구별 검색

통합 검색의 누락을 보완하기 위해 각 지구명을 단독으로 넣고 `site:apply.lh.or.kr`, `site:molit.go.kr`, 해당 지자체 도메인을 병행했다. 이 보완검색으로 고양창릉 S5, 남양주왕숙 A2, 부천대장 A8 등 블록별 직접 공고와 실제 운행 기준선 문서를 확보했다. 보완검색 결과는 두 PSV 표의 `source_url`에 직접 반영했다.
