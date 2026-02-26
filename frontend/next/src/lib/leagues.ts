export type League = {
  id: string;
  name: string;
  country: string;
  countryFlag: string;
  logo: string;
  season: string;
  totalMatches: number;
  matchesToday: number;
  apiEndpoints: {
    footystats: string;
  };
};

export type Match = {
  id: string;
  leagueId: string;
  leagueName: string;
  homeTeam: {
    name: string;
    logo: string;
    form: string[];
    rating: number;
  };
  awayTeam: {
    name: string;
    logo: string;
    form: string[];
    rating: number;
  };
  datetime: string;
  venue: string;
  status: "scheduled" | "live" | "finished" | "postponed";
  score?: {
    home: number;
    away: number;
    halftime?: { home: number; away: number };
  };
  odds: {
    home: number;
    draw: number;
    away: number;
    over15?: number;
    over25: number;
    over35?: number;
    over45?: number;
    under25: number;
    bttsYes: number;
    bttsNo: number;
    cornersOver85?: number;
    cornersOver95?: number;
    cornersOver105?: number;
    cornersOver115?: number;
  };
  stats: {
    homeWinProb: number;
    drawProb: number;
    awayWinProb: number;
    avgGoals: number;
    bttsProb: number;
    over15Prob?: number;
    over25Prob: number;
    over35Prob?: number;
    over45Prob?: number;
    over05Prob?: number;
    homePossession?: number;
    awayPossession?: number;
    homeXG?: number;
    awayXG?: number;
    homeCornersPerMatch?: number;
    awayCornersPerMatch?: number;
    homeCardsPerMatch?: number;
    awayCardsPerMatch?: number;
    homeShotsOnTarget?: number;
    awayShotsOnTarget?: number;
    homeFoulsPerMatch?: number;
    awayFoulsPerMatch?: number;
    leagueAvgCorners?: number;
    leagueAvgCards?: number;
    cornersPotential?: number;
    cornerOver85Prob?: number;
    cornerOver95Prob?: number;
    cornerOver105Prob?: number;
    lambdaHome?: number;
    lambdaAway?: number;
    lambdaTotal?: number;
    regime?: string;
    leagueRegime?: string;
    leagueVolatility?: string;
    homeForm?: string[];
    awayForm?: string[];
  };
  h2h: {
    totalMatches: number;
    homeWins: number;
    draws: number;
    awayWins: number;
    avgGoals: number;
  };
  predictions?: {
    mercado: string;
    status: string;
    prob_min: number;
    prob_max: number;
    odd_minima: number | null;
    alerta?: string;
  }[];
  source: "footystats";
  lastUpdated: string;
};

export const AVAILABLE_LEAGUES: League[] = [
  {
    id: "premier-league",
    name: "Premier League",
    country: "Inglaterra",
    countryFlag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    logo: "/logos/premier-league.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/england/premier-league",
    },
  },
  {
    id: "championship",
    name: "Championship",
    country: "Inglaterra",
    countryFlag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    logo: "/logos/championship.png",
    season: "2025/26",
    totalMatches: 552,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/england/championship",
    },
  },
  {
    id: "primera-division",
    name: "Primera Division",
    country: "Argentina",
    countryFlag: "🇦🇷",
    logo: "/logos/primera-division.png",
    season: "2026",
    totalMatches: 378,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/argentina/primera-division",
    },
  },
  {
    id: "a-league",
    name: "A-League",
    country: "Austrália",
    countryFlag: "🇦🇺",
    logo: "/logos/a-league.png",
    season: "2025/26",
    totalMatches: 162,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/australia/a-league",
    },
  },
  {
    id: "austria-bundesliga",
    name: "Bundesliga",
    country: "Áustria",
    countryFlag: "🇦🇹",
    logo: "/logos/austria-bundesliga.png",
    season: "2025/26",
    totalMatches: 132,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/austria/bundesliga",
    },
  },
  {
    id: "pro-league",
    name: "Pro League",
    country: "Bélgica",
    countryFlag: "🇧🇪",
    logo: "/logos/pro-league.png",
    season: "2025/26",
    totalMatches: 240,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/belgium/pro-league",
    },
  },
  {
    id: "brazil-serie-a",
    name: "Série A",
    country: "Brasil",
    countryFlag: "🇧🇷",
    logo: "/logos/brasileirao.png",
    season: "2026",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/brazil/campeonato-brasileiro-serie-a",
    },
  },
  {
    id: "brazil-serie-b",
    name: "Série B",
    country: "Brasil",
    countryFlag: "🇧🇷",
    logo: "/logos/brasileirao-b.png",
    season: "2026",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/brazil/campeonato-brasileiro-serie-b",
    },
  },
  {
    id: "denmark-superliga",
    name: "Superliga",
    country: "Dinamarca",
    countryFlag: "🇩🇰",
    logo: "/logos/superliga.png",
    season: "2025/26",
    totalMatches: 132,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/denmark/superliga",
    },
  },
  {
    id: "france-ligue-1",
    name: "Ligue 1",
    country: "França",
    countryFlag: "🇫🇷",
    logo: "/logos/ligue-1.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/france/ligue-1",
    },
  },
  {
    id: "france-ligue-2",
    name: "Ligue 2",
    country: "França",
    countryFlag: "🇫🇷",
    logo: "/logos/ligue-2.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/france/ligue-2",
    },
  },
  {
    id: "germany-bundesliga",
    name: "Bundesliga",
    country: "Alemanha",
    countryFlag: "🇩🇪",
    logo: "/logos/bundesliga.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/germany/bundesliga",
    },
  },
  {
    id: "germany-2-bundesliga",
    name: "2. Bundesliga",
    country: "Alemanha",
    countryFlag: "🇩🇪",
    logo: "/logos/2-bundesliga.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/germany/2-bundesliga",
    },
  },
  {
    id: "italy-serie-a",
    name: "Serie A",
    country: "Itália",
    countryFlag: "🇮🇹",
    logo: "/logos/serie-a.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/italy/serie-a",
    },
  },
  {
    id: "italy-serie-b",
    name: "Serie B",
    country: "Itália",
    countryFlag: "🇮🇹",
    logo: "/logos/serie-b.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/italy/serie-b",
    },
  },
  {
    id: "netherlands-eredivisie",
    name: "Eredivisie",
    country: "Holanda",
    countryFlag: "🇳🇱",
    logo: "/logos/eredivisie.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/netherlands/eredivisie",
    },
  },
  {
    id: "portugal-liga-nos",
    name: "Liga NOS",
    country: "Portugal",
    countryFlag: "🇵🇹",
    logo: "/logos/liga-nos.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/portugal/liga-nos",
    },
  },
  {
    id: "saudi-professional-league",
    name: "Professional League",
    country: "Arábia Saudita",
    countryFlag: "🇸🇦",
    logo: "/logos/saudi-pro-league.png",
    season: "2025/26",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/saudi-arabia/professional-league",
    },
  },
  {
    id: "scotland-premiership",
    name: "Premiership",
    country: "Escócia",
    countryFlag: "🏴󠁧󠁢󠁳󠁣󠁴󠁿",
    logo: "/logos/premiership.png",
    season: "2025/26",
    totalMatches: 228,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/scotland/premiership",
    },
  },
  {
    id: "spain-la-liga",
    name: "La Liga",
    country: "Espanha",
    countryFlag: "🇪🇸",
    logo: "/logos/laliga.png",
    season: "2025/26",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/spain/la-liga",
    },
  },
  {
    id: "switzerland-super-league",
    name: "Super League",
    country: "Suíça",
    countryFlag: "🇨🇭",
    logo: "/logos/switzerland-super-league.png",
    season: "2025/26",
    totalMatches: 132,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/switzerland/super-league",
    },
  },
  {
    id: "turkey-super-lig",
    name: "Süper Lig",
    country: "Turquia",
    countryFlag: "🇹🇷",
    logo: "/logos/super-lig.png",
    season: "2025/26",
    totalMatches: 342,
    matchesToday: 0,
    apiEndpoints: {
      footystats: "/turkey/super-lig",
    },
  },
];
