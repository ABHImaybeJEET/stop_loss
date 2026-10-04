


"use client";

import React, { useEffect, useRef, useState } from "react";
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
import {
  NewsArticle,
  CategorizedNews,
  TOP_STORIES,
  COMMODITIES_NEWS,
  INDIAN_STOCKS,
} from "@/lib/news";
import {
  ExternalLink,
  TrendingUp,
  AlertTriangle,
  ShieldAlert,
  Landmark,
  CloudLightning,
  Flame,
  Globe2,
  TrendingDown,
  Layers,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";

if (typeof window !== "undefined") {
  gsap.registerPlugin(ScrollTrigger);
}

const CATEGORY_COLORS: Record<NewsArticle["category"], { bg: string; text: string; label: string; icon: React.ReactNode }> = {
  WEATHER_EXTREME: {
    bg: "#FDEBEC",
    text: "#9F2F2D",
    label: "WEATHER DISRUPTION",
    icon: <CloudLightning className="w-3.5 h-3.5 text-[#9F2F2D]" />,
  },
  TARIFF: {
    bg: "#FBF3DB",
    text: "#956400",
    label: "TARIFF & TRADE",
    icon: <TrendingUp className="w-3.5 h-3.5 text-[#956400]" />,
  },
  WAR_CRISIS: {
    bg: "#FDEBEC",
    text: "#9F2F2D",
    label: "GEOPOLITICAL SHOCK",
    icon: <ShieldAlert className="w-3.5 h-3.5 text-[#9F2F2D]" />,
  },
  BANK_TAX: {
    bg: "#E1F3FE",
    text: "#1F6C9F",
    label: "MONETARY POLICY",
    icon: <Landmark className="w-3.5 h-3.5 text-[#1F6C9F]" />,
  },
  MACRO: {
    bg: "#EDF3EC",
    text: "#346538",
    label: "MACRO MARKET",
    icon: <AlertTriangle className="w-3.5 h-3.5 text-[#346538]" />,
  },
};

interface NewsBlockProps {
  sectionTitle: string;
  sectionSubtitle: string;
  badgeLabel: string;
  badgeIcon: React.ReactNode;
  articles: NewsArticle[];
  failedImages: Set<string>;
  onImageError: (id: string) => void;
  showTickers?: boolean;
  hideNewsCards?: boolean;
}

function NewsSectionBlock({
  sectionTitle,
  sectionSubtitle,
  badgeLabel,
  badgeIcon,
  articles,
  failedImages,
  onImageError,
  showTickers = false,
  hideNewsCards = false,
}: NewsBlockProps) {
  const blockRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const tickerRef = useRef<HTMLDivElement>(null);
  const gridRef = useRef<HTMLDivElement>(null);

  // Filter out articles with unloadable images
  const validArticles = articles.filter((a) => !failedImages.has(a.id));

  // Individual GSAP ScrollTrigger animation for each vertical section
  useEffect(() => {
    if (typeof window === "undefined" || !blockRef.current) return;

    const ctx = gsap.context(() => {
      // Header entrance
      if (headerRef.current) {
        gsap.fromTo(
          headerRef.current,
          { opacity: 0, y: 30 },
          {
            opacity: 1,
            y: 0,
            duration: 0.6,
            ease: "power3.out",
            scrollTrigger: {
              trigger: headerRef.current,
              start: "top 85%",
              toggleActions: "play none none reverse",
            },
          }
        );
      }

      // Stock Tickers entrance if present
      if (tickerRef.current) {
        gsap.fromTo(
          tickerRef.current.children,
          { opacity: 0, scale: 0.96, y: 15 },
          {
            opacity: 1,
            scale: 1,
            y: 0,
            duration: 0.5,
            stagger: 0.05,
            ease: "power2.out",
            scrollTrigger: {
              trigger: tickerRef.current,
              start: "top 88%",
              toggleActions: "play none none reverse",
            },
          }
        );
      }

      // Card Grid staggered entrance animation
      if (gridRef.current) {
        const cards = gridRef.current.children;
        if (cards.length > 0) {
          gsap.fromTo(
            cards,
            { opacity: 0, y: 45 },
            {
              opacity: 1,
              y: 0,
              duration: 0.65,
              stagger: 0.08,
              ease: "power3.out",
              scrollTrigger: {
                trigger: gridRef.current,
                start: "top 85%",
                toggleActions: "play none none reverse",
              },
            }
          );
        }
      }
    }, blockRef);

    return () => ctx.revert();
  }, [validArticles.length]);

  if (validArticles.length === 0) {
    return null;
  }

  return (
    <div ref={blockRef} className="mb-24 last:mb-0">
      {/* Sub-section Header */}
      <div ref={headerRef} className="mb-8 border-b border-[#EAEAEA] pb-5 flex flex-row items-end justify-between gap-4">
        <div>
          <div className="inline-flex items-center space-x-2 bg-[#F7F6F3] border border-[#EAEAEA] px-3 py-1 rounded-full text-xs font-mono text-[#111111] font-semibold mb-3">
            {badgeIcon}
            <span>{badgeLabel}</span>
          </div>
          <h3 className="text-xl md:text-3xl font-bold tracking-tight text-[#111111]">
            {sectionTitle}
          </h3>
          <p className="text-xs md:text-sm text-[#787774] mt-1 max-w-2xl leading-relaxed">
            {sectionSubtitle}
          </p>
        </div>

        {showTickers && (
          <div className="flex items-center space-x-1.5 shrink-0 mb-1">
            <button
              onClick={() => tickerRef.current?.scrollBy({ left: -260, behavior: "smooth" })}
              className="w-7 h-7 rounded border border-[#EAEAEA] bg-white text-[#111111] hover:border-black hover:bg-black hover:text-white transition-colors flex items-center justify-center shadow-xs cursor-pointer"
              aria-label="Scroll Left"
              title="Scroll Left"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => tickerRef.current?.scrollBy({ left: 260, behavior: "smooth" })}
              className="w-7 h-7 rounded border border-[#EAEAEA] bg-white text-[#111111] hover:border-black hover:bg-black hover:text-white transition-colors flex items-center justify-center shadow-xs cursor-pointer"
              aria-label="Scroll Right"
              title="Scroll Right"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* Single Row Horizontally Scrollable Stock Ticker Banner */}
      {showTickers && (
        <div className="relative mb-8">
          <div
            ref={tickerRef}
            className="flex items-stretch space-x-3.5 overflow-x-auto pb-4 pt-1 no-scrollbar scroll-smooth [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden snap-x select-none border-b border-[#F7F6F3]"
          >
            {validArticles.map((stock) => (
              <a
                key={`ticker-${stock.id}`}
                href={stock.url}
                target="_blank"
                rel="noopener noreferrer"
                className="min-w-[210px] w-[210px] shrink-0 bg-white border border-[#EAEAEA] p-4 rounded-xl hover:border-black transition-all duration-300 flex flex-col justify-between group shadow-sm hover:shadow-md hover:-translate-y-0.5 snap-start"
              >
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-mono font-extrabold text-xs text-[#111111] group-hover:text-orange-600 transition-colors">
                      {stock.ticker}
                    </span>
                  </div>
                  <div className="text-[11px] font-sans font-medium text-[#787774] truncate mb-2.5">
                    {stock.companyName || stock.ticker}
                  </div>
                </div>

                {/* Price & Change */}
                <div className="pt-2 border-t border-[#F7F6F3]">
                  <div className="text-xs font-mono font-bold text-[#111111] tracking-tight">
                    ₹{stock.priceInr} <span className="text-[10px] text-[#787774] font-normal">INR</span>
                  </div>
                  <div className="flex items-center justify-between mt-1.5">
                    <span
                      className={`inline-flex items-center space-x-1 text-[11px] font-mono font-bold ${
                        stock.isPositive ? "text-emerald-600" : "text-rose-600"
                      }`}
                    >
                      {stock.isPositive ? (
                        <TrendingUp className="w-3 h-3" />
                      ) : (
                        <TrendingDown className="w-3 h-3" />
                      )}
                      <span>{stock.changePercent}</span>
                    </span>
                    {stock.sector && (
                      <span className="text-[9px] font-mono text-[#A1A09A] uppercase tracking-tighter truncate max-w-[70px]">
                        {stock.sector}
                      </span>
                    )}
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Grid of Unique News Cards */}
      {!hideNewsCards && (
        <div ref={gridRef} className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {validArticles.map((article) => {
            const cat = CATEGORY_COLORS[article.category] || CATEGORY_COLORS.MACRO;

            return (
              <article
                key={article.id}
                className="group bg-white border border-[#EAEAEA] rounded-lg overflow-hidden flex flex-col justify-between transition-all duration-300 hover:border-[#111111] hover:shadow-[0_4px_24px_rgba(0,0,0,0.06)]"
              >
                <div>
                  {/* Card Thumbnail Image (Load error handled to eliminate unloadable images) */}
                  <div className="relative w-full aspect-[16/9] overflow-hidden bg-[#F7F6F3]">
                    <img
                      src={article.imageUrl}
                      alt={article.title}
                      className="w-full h-full object-cover group-hover:scale-105 transition-all duration-500"
                      loading="lazy"
                      onError={() => onImageError(article.id)}
                    />
                  </div>

                  {/* Content Container */}
                  <div className="p-6">
                    {/* Category & Source Meta Info */}
                    <div className="flex items-center justify-between text-xs font-mono mb-3">
                      <span className="inline-flex items-center space-x-1.5 font-bold text-[#111111] uppercase tracking-wider text-[11px]">
                        {cat.icon}
                        <span>{cat.label}</span>
                      </span>
                      <span className="text-[#787774] font-mono text-[11px]">
                        {article.source} • {article.publishedAt}
                      </span>
                    </div>

                    {/* Optional Stock Ticker Badge */}
                    {article.ticker && (
                      <div className="mb-3 inline-flex items-center space-x-2 bg-[#F7F6F3] border border-[#EAEAEA] px-2.5 py-1 rounded text-xs font-mono">
                        <span className="font-bold text-[#111111]">{article.ticker}</span>
                        <span className="text-[#787774]">₹{article.priceInr}</span>
                        <span
                          className={
                            article.isPositive ? "text-emerald-600 font-semibold" : "text-rose-600 font-semibold"
                          }
                        >
                          {article.changePercent}
                        </span>
                      </div>
                    )}

                    <h4 className="text-base font-bold text-[#111111] tracking-tight leading-snug mb-2.5 group-hover:text-black transition-colors">
                      {article.title}
                    </h4>

                    <p className="text-xs text-[#787774] leading-relaxed font-normal line-clamp-3">
                      {article.summary}
                    </p>
                  </div>
                </div>

                {/* Footer Link Button */}
                <div className="px-6 pb-6 pt-3 border-t border-[#F7F6F3] flex items-center justify-between mt-2">
                  <span className="text-[11px] font-mono text-[#A1A09A]">VERIFIED RECORD</span>
                  <a
                    href={article.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center space-x-1.5 bg-[#111111] text-white px-3.5 py-1.5 text-xs font-semibold uppercase tracking-wider rounded border border-[#111111] hover:bg-[#333333] transition-colors"
                  >
                    <span>READ</span>
                    <ExternalLink className="w-3 h-3 ml-0.5" />
                  </a>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function NewsSection() {
  const [data, setData] = useState<CategorizedNews>({
    topStories: TOP_STORIES,
    commodities: COMMODITIES_NEWS,
    indianStocks: INDIAN_STOCKS,
  });

  // Track failed image IDs so broken images are filtered out completely
  const [failedImages, setFailedImages] = useState<Set<string>>(new Set());

  const mainSectionRef = useRef<HTMLElement>(null);
  const mainHeaderRef = useRef<HTMLDivElement>(null);

  const [isApiLoading, setIsApiLoading] = useState<boolean>(true);
  const [isUsingFallback, setIsUsingFallback] = useState<boolean>(false);

  useEffect(() => {
    async function loadNews() {
      setIsApiLoading(true);
      try {
        const res = await fetch(`/api/news?t=${Date.now()}`, { cache: 'no-store' });
        if (res.ok) {
          const json = await res.json();
          if (json.topStories && json.topStories.length > 0) {
            setData(json);
            setIsUsingFallback(false);
          }
        } else {
          setIsUsingFallback(true);
        }
      } catch (err) {
        console.warn("Market feed unavailable:", err);
        setIsUsingFallback(true);
      } finally {
        setIsApiLoading(false);
      }
    }

    loadNews();
  }, []);

  // Main Header GSAP Animation
  useEffect(() => {
    if (typeof window === "undefined" || !mainHeaderRef.current) return;

    const ctx = gsap.context(() => {
      gsap.fromTo(
        mainHeaderRef.current,
        { opacity: 0, y: 35 },
        {
          opacity: 1,
          y: 0,
          duration: 0.7,
          ease: "power3.out",
          scrollTrigger: {
            trigger: mainHeaderRef.current,
            start: "top 85%",
            toggleActions: "play none none reverse",
          },
        }
      );
    }, mainSectionRef);

    return () => ctx.revert();
  }, []);

  const handleImageError = (id: string) => {
    setFailedImages((prev) => {
      const updated = new Set(prev);
      updated.add(id);
      return updated;
    });
  };

  // Proactively test-load all article images to instantly remove broken photo cards
  useEffect(() => {
    const allArticles = [...data.topStories, ...data.commodities, ...data.indianStocks];
    allArticles.forEach((art) => {
      if (!art.imageUrl) {
        handleImageError(art.id);
        return;
      }
      const img = new Image();
      img.src = art.imageUrl;
      img.onerror = () => {
        handleImageError(art.id);
      };
    });
  }, [data]);

  // Ensure unique articles across all sections (no repeating cards)
  const renderIds = new Set<string>();

  const uniqueTopStories = data.topStories.filter((art) => {
    if (renderIds.has(art.id)) return false;
    renderIds.add(art.id);
    return true;
  });

  const uniqueCommodities = data.commodities.filter((art) => {
    if (renderIds.has(art.id)) return false;
    renderIds.add(art.id);
    return true;
  });

  const uniqueIndianStocks = data.indianStocks.filter((art) => {
    if (renderIds.has(art.id)) return false;
    renderIds.add(art.id);
    return true;
  });

  return (
    <section
      ref={mainSectionRef}
      id="intelligence-feed"
      className="w-full bg-[#FAFAFA] border-t border-[#EAEAEA] py-20 px-6 md:px-12 relative z-10 font-sans"
    >
      <div className="max-w-6xl mx-auto">
        {/* Main Title Section */}
        <div ref={mainHeaderRef} className="mb-14 border-b border-[#EAEAEA] pb-6 flex flex-col md:flex-row md:items-end justify-between gap-4">
          <div>
            <div className="inline-flex items-center space-x-2 bg-[#111111] text-white px-3 py-1 rounded text-xs font-mono uppercase tracking-widest font-semibold mb-3">
              <Layers className="w-3.5 h-3.5" />
              <span>Financial Intelligence Feed</span>
            </div>
            <h2 className="text-2xl md:text-4xl font-bold tracking-tight text-[#111111]">
              Market Intelligence
            </h2>
            <p className="text-xs md:text-sm text-[#787774] mt-1.5 max-w-2xl leading-relaxed">
              Real-time verified feeds tracking macro economic shocks, energy disruptions, and Indian equity prices.
            </p>
          </div>

        </div>

        {/* Vertical Section 1: Top Stories */}
        <NewsSectionBlock
          sectionTitle="Top Stories"
          sectionSubtitle="Global headlines, rate policy shifts, trade tariffs, and cross-border market movements."
          badgeLabel="GLOBAL HEADLINES"
          badgeIcon={<Globe2 className="w-3.5 h-3.5 text-[#111111]" />}
          articles={uniqueTopStories}
          failedImages={failedImages}
          onImageError={handleImageError}
        />

        {/* Vertical Section 2: Commodities News */}
        <NewsSectionBlock
          sectionTitle="Commodities"
          sectionSubtitle="Coastal hurricane impacts, crude oil production shifts, bullion reserves, and industrial metal prices."
          badgeLabel="ENERGY & METALS"
          badgeIcon={<Flame className="w-3.5 h-3.5 text-amber-600" />}
          articles={uniqueCommodities}
          failedImages={failedImages}
          onImageError={handleImageError}
        />

        {/* Vertical Section 3: Indian Stocks */}
        <NewsSectionBlock
          sectionTitle="Indian Stocks"
          sectionSubtitle="Live Nifty & Sensex equity constituents, corporate earnings, infrastructure capex surge, and INR market price quotes."
          badgeLabel="NSE / BSE INDIA"
          badgeIcon={<TrendingUp className="w-3.5 h-3.5 text-emerald-600" />}
          articles={uniqueIndianStocks}
          failedImages={failedImages}
          onImageError={handleImageError}
          showTickers={true}
          hideNewsCards={true}
        />
      </div>
    </section>
  );
}
