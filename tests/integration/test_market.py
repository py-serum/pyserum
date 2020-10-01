# pylint: disable=redefined-outer-name

import pytest
from solana.account import Account
from solana.publickey import PublicKey
from solana.rpc.api import Client

from pyserum.enums import OrderType, Side
from pyserum.market import Market

from .utils import confirm_transaction


@pytest.mark.integration
@pytest.fixture(scope="module")
def bootstrapped_market(http_client: Client, stubbed_market_pk: PublicKey, stubbed_dex_program_pk: PublicKey) -> Market:
    return Market.load(http_client, stubbed_market_pk, stubbed_dex_program_pk)


@pytest.mark.integration
def test_bootstrapped_market(
    bootstrapped_market: Market,
    stubbed_market_pk: PublicKey,
    stubbed_dex_program_pk: PublicKey,
    stubbed_base_mint: PublicKey,
    stubbed_quote_mint: PublicKey,
):
    assert isinstance(bootstrapped_market, Market)
    assert bootstrapped_market.state.public_key() == stubbed_market_pk
    assert bootstrapped_market.state.program_id() == stubbed_dex_program_pk
    assert bootstrapped_market.state.base_mint() == stubbed_base_mint.public_key()
    assert bootstrapped_market.state.quote_mint() == stubbed_quote_mint.public_key()


@pytest.mark.integration
def test_market_load_bid(bootstrapped_market: Market):
    # TODO: test for non-zero order case.
    bids = bootstrapped_market.load_bids()
    assert sum(1 for _ in bids) == 0


@pytest.mark.integration
def test_market_load_asks(bootstrapped_market: Market):
    # TODO: test for non-zero order case.
    asks = bootstrapped_market.load_asks()
    assert sum(1 for _ in asks) == 0


@pytest.mark.integration
def test_market_load_events(bootstrapped_market: Market):
    event_queue = bootstrapped_market.load_event_queue()
    assert len(event_queue) == 0


@pytest.mark.integration
def test_market_load_requests(bootstrapped_market: Market):
    request_queue = bootstrapped_market.load_request_queue()
    # 2 requests in the request queue in the beginning with one bid and one ask
    assert len(request_queue) == 2


@pytest.mark.integration
def test_match_order(bootstrapped_market: Market, stubbed_payer: Account, http_client: Client):
    sig = bootstrapped_market.match_orders(stubbed_payer, 2)
    confirm_transaction(http_client, sig)

    request_queue = bootstrapped_market.load_request_queue()
    # 0 request after matching.
    assert len(request_queue) == 0

    event_queue = bootstrapped_market.load_event_queue()
    # 5 event after the order is matched, including 2 fill events.
    assert len(event_queue) == 5

    # There should be no bid order.
    bids = bootstrapped_market.load_bids()
    assert sum(1 for _ in bids) == 0

    # There should be no ask order.
    asks = bootstrapped_market.load_asks()
    assert sum(1 for _ in asks) == 0


@pytest.mark.integration
def test_order_placement_cancellation_cycle(
    bootstrapped_market: Market,
    stubbed_payer: Account,
    http_client: Client,
    stubbed_quote_wallet: Account,
    stubbed_base_wallet: Account,
):
    initial_request_len = len(bootstrapped_market.load_request_queue())
    sig = bootstrapped_market.place_order(
        payer=stubbed_quote_wallet.public_key(),
        owner=stubbed_payer,
        side=Side.Buy,
        order_type=OrderType.Limit,
        limit_price=1000,
        max_quantity=3000,
    )
    confirm_transaction(http_client, sig)

    request_queue = bootstrapped_market.load_request_queue()
    # 0 request after matching.
    assert len(request_queue) == initial_request_len + 1

    # There should be no bid order.
    bids = bootstrapped_market.load_bids()
    assert sum(1 for _ in bids) == 0

    # There should be no ask order.
    asks = bootstrapped_market.load_asks()
    assert sum(1 for _ in asks) == 0

    sig = bootstrapped_market.place_order(
        payer=stubbed_base_wallet.public_key(),
        owner=stubbed_payer,
        side=Side.Sell,
        order_type=OrderType.Limit,
        limit_price=1500,
        max_quantity=3000,
    )
    confirm_transaction(http_client, sig)

    # The two order shouldn't get executed since there is a price difference of 1
    sig = bootstrapped_market.match_orders(stubbed_payer, 2)
    confirm_transaction(http_client, sig)

    # There should be 1 bid order that we sent earlier.
    bids = bootstrapped_market.load_bids()
    assert sum(1 for _ in bids) == 1

    # There should be 1 ask order that we sent earlier.
    asks = bootstrapped_market.load_asks()
    assert sum(1 for _ in asks) == 1

    for bid in bids:
        sig = bootstrapped_market.cancel_order(stubbed_payer, bid)
        confirm_transaction(http_client, sig)

    sig = bootstrapped_market.match_orders(stubbed_payer, 1)
    confirm_transaction(http_client, sig)

    # All bid order should have been cancelled.
    bids = bootstrapped_market.load_bids()
    assert sum(1 for _ in bids) == 0

    for ask in asks:
        sig = bootstrapped_market.cancel_order(stubbed_payer, ask)
        confirm_transaction(http_client, sig)

    sig = bootstrapped_market.match_orders(stubbed_payer, 1)
    confirm_transaction(http_client, sig)

    # All ask order should have been cancelled.
    asks = bootstrapped_market.load_asks()
    assert sum(1 for _ in asks) == 0
