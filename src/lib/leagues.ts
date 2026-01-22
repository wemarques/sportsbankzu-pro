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
    whoscored: string;
    footystats: string;
    packball: string;
  };
};

export const AVAILABLE_LEAGUES: League[] = [
  {
    id: "brasileirao-a",
    name: "Campeonato Brasileiro Série A",
    country: "Brasil",
    countryFlag: "🇧🇷",
    logo: "/logos/brasileirao.png",
    season: "2024",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/31/tournaments/95",
      footystats: "/brazil/campeonato-brasileiro-serie-a",
      packball: "/matches?league=brasileirao",
    },
  },
  {
    id: "premier-league",
    name: "Premier League",
    country: "Inglaterra",
    countryFlag: "🏴",
    logo: "/logos/premier-league.png",
    season: "2024/25",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/252/tournaments/2",
      footystats: "/england/premier-league",
      packball: "/matches?league=premier-league",
    },
  },
  {
    id: "la-liga",
    name: "La Liga",
    country: "Espanha",
    countryFlag: "🇪🇸",
    logo: "/logos/laliga.png",
    season: "2024/25",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/206/tournaments/4",
      footystats: "/spain/la-liga",
      packball: "/matches?league=la-liga",
    },
  },
  {
    id: "serie-a",
    name: "Serie A",
    country: "Itália",
    countryFlag: "🇮🇹",
    logo: "/logos/serie-a.png",
    season: "2024/25",
    totalMatches: 380,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/108/tournaments/5",
      footystats: "/italy/serie-a",
      packball: "/matches?league=serie-a",
    },
  },
  {
    id: "bundesliga",
    name: "Bundesliga",
    country: "Alemanha",
    countryFlag: "🇩🇪",
    logo: "/logos/bundesliga.png",
    season: "2024/25",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/81/tournaments/3",
      footystats: "/germany/bundesliga",
      packball: "/matches?league=bundesliga",
    },
  },
  {
    id: "ligue-1",
    name: "Ligue 1",
    country: "França",
    countryFlag: "🇫🇷",
    logo: "/logos/ligue-1.png",
    season: "2024/25",
    totalMatches: 306,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/74/tournaments/22",
      footystats: "/france/ligue-1",
      packball: "/matches?league=ligue-1",
    },
  },
  {
    id: "champions-league",
    name: "UEFA Champions League",
    country: "Europa",
    countryFlag: "🇪🇺",
    logo: "/logos/ucl.png",
    season: "2024/25",
    totalMatches: 189,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/250/tournaments/12",
      footystats: "/europe/uefa-champions-league",
      packball: "/matches?league=champions-league",
    },
  },
  {
    id: "copa-libertadores",
    name: "Copa Libertadores",
    country: "América do Sul",
    countryFlag: "🌎",
    logo: "/logos/libertadores.png",
    season: "2024",
    totalMatches: 150,
    matchesToday: 0,
    apiEndpoints: {
      whoscored: "/regions/247/tournaments/384",
      footystats: "/south-america/copa-libertadores",
      packball: "/matches?league=libertadores",
    },
  },
];

