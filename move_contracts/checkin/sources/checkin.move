module movectf::checkin {
    use sui::event;
    use sui::transfer;
    use sui::object::{Self, UID};
    use sui::tx_context::{Self, TxContext};

    struct Counter has key, store {
        id: UID,
        value: u64,
    }

    struct Flag has copy, drop {
        user: address,
        flag: bool
    }

    public entry fun getCounter(ctx: &mut TxContext) {
        let sender = tx_context::sender(ctx);
        let counter_obj = Counter {
            id: object::new(ctx),
            value: 0
        };
        transfer::transfer(counter_obj, sender);
    }

    public entry fun addone(counter: &mut Counter) {
        counter.value = counter.value + 1;
    }

    public entry fun isSolved(counter: &mut Counter, ctx: &mut TxContext) {
        if (counter.value != 0) {
            event::emit(Flag {
            user: tx_context::sender(ctx),
            flag: true
        })
       }
    }
}