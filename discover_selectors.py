#!/usr/bin/env python3
"""
Selector Discovery Script for Polymarket NBA Games - v2

This script helps identify the correct CSS selectors for:
1. Game cards on the main NBA games page
2. Navigation elements (Game View, Moneyline, Graph, 6H tabs)
3. Price elements
4. Graph elements for screenshots

Run with: python3 discover_selectors.py
"""

import json
import time
from datetime import datetime
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, ElementHandle
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

OUTPUT_DIR = Path("discovery_output")
OUTPUT_DIR.mkdir(exist_ok=True)


def save_screenshot(page: Page, name: str) -> str:
    """Save a screenshot and return the path."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{name}_{timestamp}.png"
    page.screenshot(path=str(path), full_page=False)
    return str(path)


def analyze_element(element: ElementHandle, depth: int = 0) -> dict:
    """Analyze an element and return its properties."""
    try:
        tag = element.evaluate("el => el.tagName.toLowerCase()")
        classes = element.evaluate("el => el.className")
        text = element.evaluate("el => el.innerText?.slice(0, 100) || ''")
        href = element.evaluate("el => el.href || ''")
        data_attrs = element.evaluate("""el => {
            const attrs = {};
            for (const attr of el.attributes) {
                if (attr.name.startsWith('data-')) {
                    attrs[attr.name] = attr.value;
                }
            }
            return attrs;
        }""")
        return {
            "tag": tag,
            "classes": classes[:200] if classes else "",
            "text": text.strip()[:100] if text else "",
            "href": href,
            "data_attrs": data_attrs
        }
    except Exception as e:
        return {"error": str(e)}


def discover_games_page(page: Page) -> dict:
    """Discover selectors on the main NBA games page."""
    console.print("\n[bold blue]Analyzing NBA Games Page...[/bold blue]")

    results = {
        "url": page.url,
        "game_cards": [],
        "game_view_buttons": [],
        "moneyline_prices": [],
        "potential_selectors": {}
    }

    # Wait for page to fully load
    page.wait_for_load_state("networkidle")
    console.print("[yellow]Waiting for dynamic content to load...[/yellow]")
    time.sleep(5)  # Extra wait for dynamic content

    # Save screenshot of games page
    ss_path = save_screenshot(page, "games_page")
    console.print(f"[green]Screenshot saved:[/green] {ss_path}")

    # Look for "Game View" buttons/links - these identify game rows
    console.print("\n[bold]Looking for 'Game View' elements...[/bold]")
    game_view_elements = page.get_by_text("Game View").all()
    console.print(f"[green]Found {len(game_view_elements)} 'Game View' elements[/green]")

    for i, el in enumerate(game_view_elements[:5]):
        try:
            # Get parent container which should be the game row
            parent_info = el.evaluate("""el => {
                // Go up to find the game row container
                let parent = el.parentElement;
                for (let i = 0; i < 10 && parent; i++) {
                    parent = parent.parentElement;
                }
                return {
                    tag: parent?.tagName?.toLowerCase() || 'unknown',
                    classes: parent?.className || '',
                    html: parent?.outerHTML?.slice(0, 500) || ''
                };
            }""")
            results["game_view_buttons"].append({
                "index": i,
                "parent_info": parent_info
            })
            console.print(f"  Game View {i+1}: parent classes = {parent_info.get('classes', '')[:100]}")
        except Exception as e:
            console.print(f"[red]Error analyzing Game View {i+1}:[/red] {e}")

    # Look for moneyline price buttons (colored buttons with prices)
    console.print("\n[bold]Looking for moneyline price elements...[/bold]")

    # Find buttons containing cent prices
    price_buttons = page.evaluate("""() => {
        const buttons = document.querySelectorAll('button');
        const results = [];
        for (const btn of buttons) {
            const text = btn.innerText;
            if (text && text.includes('¢')) {
                results.push({
                    text: text.trim(),
                    classes: btn.className,
                    bgColor: getComputedStyle(btn).backgroundColor
                });
            }
        }
        return results;
    }""")

    results["moneyline_prices"] = price_buttons
    console.print(f"[green]Found {len(price_buttons)} price buttons[/green]")
    for p in price_buttons[:6]:
        console.print(f"  Price: {p['text']}, BG: {p['bgColor'][:50]}")

    # Look for team name elements
    console.print("\n[bold]Looking for team elements...[/bold]")
    team_elements = page.evaluate("""() => {
        // Look for elements with team abbreviations or names
        const teams = ['SAC', 'IND', 'PHX', 'MIN', 'SAS', 'NOP', 'MIA', 'ORL',
                       'LAL', 'BOS', 'GSW', 'NYK', 'BKN', 'MIL', 'DAL', 'DEN'];
        const results = [];
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
            const text = walker.currentNode.textContent.trim();
            for (const team of teams) {
                if (text === team || text.startsWith(team + ' ')) {
                    const parent = walker.currentNode.parentElement;
                    results.push({
                        team: team,
                        text: text,
                        tag: parent.tagName.toLowerCase(),
                        classes: parent.className
                    });
                    break;
                }
            }
        }
        return results.slice(0, 20);
    }""")

    console.print(f"[green]Found {len(team_elements)} team elements[/green]")
    for t in team_elements[:6]:
        console.print(f"  Team: {t['team']}, tag: {t['tag']}")

    # Find the first "Game View" link and extract its href or click behavior
    console.print("\n[bold]Analyzing first Game View link...[/bold]")
    try:
        first_game_view = page.get_by_text("Game View").first
        # Find the clickable parent (likely an anchor or button)
        game_view_link = page.evaluate("""() => {
            const el = document.evaluate(
                "//*[contains(text(), 'Game View')]",
                document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue;

            if (!el) return null;

            // Look for parent anchor
            let parent = el;
            for (let i = 0; i < 5 && parent; i++) {
                if (parent.tagName === 'A' && parent.href) {
                    return { type: 'link', href: parent.href };
                }
                parent = parent.parentElement;
            }

            return { type: 'button', text: el.innerText };
        }""")

        results["first_game_view_link"] = game_view_link
        console.print(f"[green]First Game View:[/green] {game_view_link}")
    except Exception as e:
        console.print(f"[yellow]Could not analyze Game View link:[/yellow] {e}")

    return results


def discover_game_page(page: Page) -> dict:
    """Discover selectors on a specific game page by clicking Game View."""
    console.print(f"\n[bold blue]Navigating to Game Page...[/bold blue]")

    results = {
        "tabs": [],
        "prices": [],
        "graph_selectors": [],
        "time_periods": []
    }

    # Click the first "Game View" button
    try:
        game_view = page.get_by_text("Game View").first
        game_view.click()
        console.print("[green]Clicked 'Game View'[/green]")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        results["url"] = page.url
        ss_path = save_screenshot(page, "game_page_initial")
        console.print(f"[green]Screenshot saved:[/green] {ss_path}")
    except Exception as e:
        console.print(f"[red]Error clicking Game View:[/red] {e}")
        return results

    # Look for market type tabs (Moneyline, Spread, Total, etc.)
    console.print("\n[bold]Looking for market tabs...[/bold]")
    market_tabs = page.evaluate("""() => {
        const tabs = [];
        const buttons = document.querySelectorAll('button');
        for (const btn of buttons) {
            const text = btn.innerText.trim();
            if (['Moneyline', 'Spread', 'Total', 'Player Props'].some(t => text.includes(t))) {
                tabs.push({
                    text: text,
                    classes: btn.className,
                    isSelected: btn.getAttribute('aria-selected') === 'true' ||
                               btn.className.includes('selected') ||
                               btn.getAttribute('data-state') === 'active'
                });
            }
        }
        return tabs;
    }""")

    results["market_tabs"] = market_tabs
    console.print(f"[green]Found market tabs:[/green] {[t['text'] for t in market_tabs]}")

    # Click on Moneyline tab if not already selected
    console.print("\n[bold]Looking for and clicking Moneyline...[/bold]")
    try:
        moneyline = page.get_by_text("Moneyline", exact=True).first
        if moneyline:
            moneyline.click()
            time.sleep(2)
            ss_path = save_screenshot(page, "after_moneyline")
            console.print(f"[green]Screenshot after Moneyline click:[/green] {ss_path}")
    except Exception as e:
        console.print(f"[yellow]Moneyline click issue:[/yellow] {e}")

    # Look for Graph tab
    console.print("\n[bold]Looking for Graph tab...[/bold]")
    try:
        graph_tab = page.get_by_text("Graph", exact=True).first
        if graph_tab:
            graph_tab.click()
            time.sleep(2)
            ss_path = save_screenshot(page, "after_graph")
            console.print(f"[green]Screenshot after Graph click:[/green] {ss_path}")

            # Look for time period buttons (6H, 1D, 1W, etc.)
            console.print("\n[bold]Looking for time period selectors...[/bold]")
            time_buttons = page.evaluate("""() => {
                const buttons = [];
                document.querySelectorAll('button').forEach(btn => {
                    const text = btn.innerText.trim();
                    if (['6H', '1D', '1W', '1M', 'ALL', '24H'].includes(text)) {
                        buttons.push({
                            text: text,
                            classes: btn.className,
                            selector: `button:has-text("${text}")`
                        });
                    }
                });
                return buttons;
            }""")

            results["time_periods"] = time_buttons
            console.print(f"[green]Found time periods:[/green] {[t['text'] for t in time_buttons]}")

            # Click 6H if available
            try:
                six_h = page.get_by_text("6H", exact=True).first
                if six_h:
                    six_h.click()
                    time.sleep(2)
                    ss_path = save_screenshot(page, "after_6h")
                    console.print(f"[green]Screenshot after 6H click:[/green] {ss_path}")
            except Exception as e:
                console.print(f"[yellow]6H click issue:[/yellow] {e}")

    except Exception as e:
        console.print(f"[yellow]Graph tab issue:[/yellow] {e}")

    # Look for chart/graph elements
    console.print("\n[bold]Looking for chart elements...[/bold]")
    chart_info = page.evaluate("""() => {
        const charts = [];

        // SVG charts
        document.querySelectorAll('svg').forEach((svg, i) => {
            if (svg.querySelector('path') && svg.clientHeight > 50) {
                charts.push({
                    type: 'svg',
                    index: i,
                    width: svg.clientWidth,
                    height: svg.clientHeight,
                    classes: svg.className?.baseVal || ''
                });
            }
        });

        // Canvas charts
        document.querySelectorAll('canvas').forEach((canvas, i) => {
            if (canvas.clientHeight > 50) {
                charts.push({
                    type: 'canvas',
                    index: i,
                    width: canvas.clientWidth,
                    height: canvas.clientHeight
                });
            }
        });

        // Recharts or other chart containers
        document.querySelectorAll('[class*="chart"], [class*="Chart"], [class*="recharts"]').forEach((el, i) => {
            charts.push({
                type: 'container',
                index: i,
                tag: el.tagName.toLowerCase(),
                classes: el.className,
                width: el.clientWidth,
                height: el.clientHeight
            });
        });

        return charts;
    }""")

    results["chart_elements"] = chart_info
    console.print(f"[green]Found {len(chart_info)} potential chart elements[/green]")
    for c in chart_info:
        console.print(f"  {c['type']}: {c.get('width', '?')}x{c.get('height', '?')}")

    # Look for current prices on the graph page
    console.print("\n[bold]Looking for price elements on graph page...[/bold]")
    prices = page.evaluate("""() => {
        const results = [];
        const walk = (node) => {
            if (node.nodeType === Node.TEXT_NODE && node.textContent.includes('¢')) {
                const parent = node.parentElement;
                results.push({
                    text: parent.innerText.trim(),
                    tag: parent.tagName.toLowerCase(),
                    classes: parent.className?.slice(0, 100) || ''
                });
            }
            for (const child of node.childNodes) {
                walk(child);
            }
        };
        walk(document.body);
        return results.slice(0, 10);
    }""")

    results["graph_page_prices"] = prices
    for p in prices[:5]:
        console.print(f"  Price: {p['text']}")

    return results


def main():
    console.print(Panel.fit(
        "[bold green]Polymarket Selector Discovery Script v2[/bold green]\n"
        "This will open a browser and analyze the page structure.",
        title="Discovery Tool"
    ))

    all_results = {}

    with sync_playwright() as p:
        # Launch browser in headed mode
        browser = p.chromium.launch(headless=False, slow_mo=300)
        context = browser.new_context(viewport={"width": 1920, "height": 1080})
        page = context.new_page()

        # Navigate to NBA games page
        console.print("\n[bold]Navigating to Polymarket NBA games...[/bold]")
        page.goto("https://polymarket.com/sports/nba/games")

        # Discover games page selectors
        games_results = discover_games_page(page)
        all_results["games_page"] = games_results

        # Discover game page selectors by clicking into a game
        game_results = discover_game_page(page)
        all_results["game_page"] = game_results

        # Save results to JSON
        output_path = OUTPUT_DIR / "selector_discovery_results.json"
        with open(output_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        console.print(f"\n[bold green]Results saved to:[/bold green] {output_path}")

        # Keep browser open for manual inspection
        console.print("\n[bold yellow]Browser will stay open for 20 seconds for manual inspection...[/bold yellow]")
        console.print("Press Ctrl+C to close earlier.")
        try:
            time.sleep(20)
        except KeyboardInterrupt:
            pass

        browser.close()

    # Print summary
    console.print("\n")
    console.print(Panel.fit(
        "[bold]Discovery Complete![/bold]\n\n"
        f"Screenshots saved to: {OUTPUT_DIR}/\n"
        f"Results JSON: {output_path}\n\n"
        "Review the screenshots and JSON to identify the correct selectors.",
        title="Summary"
    ))


if __name__ == "__main__":
    main()
